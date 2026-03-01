"""Step 4.7: 하이브리드 검색 오케스트레이터.

전체 검색 파이프라인 조립:
  HyDE(선택) → 임베딩 → 병렬 검색(벡터+키워드) → RRF 결합 → 리랭킹(선택) → 답변 생성(선택)
"""
from __future__ import annotations

import asyncio
import time

from app.config import RAGSettings
from app.models.schemas import PipelineStep, SearchPipelineResult, SearchResult
from app.services.embedding.base import EmbeddingProvider
from app.services.generation.base import LLMProvider
from app.services.generation.prompts import SYSTEM_PROMPT, build_prompt
from app.services.hyde.generator import HyDEGenerator
from app.services.reranking.base import Reranker
from app.services.search.rrf import RRFCombiner


class HybridSearchOrchestrator:
    """하이브리드 검색 오케스트레이터.

    벡터 검색, 키워드 검색, RRF 결합, 리랭킹, HyDE, 답변 생성을
    설정에 따라 동적으로 조합하여 실행한다.
    """

    def __init__(
        self,
        embedder: EmbeddingProvider,
        vector_engine,
        keyword_engine,
        reranker: Reranker,
        hyde_generator: HyDEGenerator,
        llm: LLMProvider,
    ) -> None:
        self.embedder = embedder
        self.vector_engine = vector_engine
        self.keyword_engine = keyword_engine
        self.reranker = reranker
        self.hyde = hyde_generator
        self.llm = llm
        self.rrf = RRFCombiner()

    async def search(
        self,
        query: str,
        settings: RAGSettings,
        generate_answer: bool = True,
    ) -> SearchPipelineResult:
        """전체 검색 파이프라인을 실행한다.

        Args:
            query: 사용자 검색 쿼리.
            settings: RAG 런타임 설정.
            generate_answer: True이면 LLM 답변 생성 포함.

        Returns:
            SearchPipelineResult(documents, answer, trace).
        """
        trace: list[PipelineStep] = []

        # 1. HyDE (선택적)
        search_query = query
        if settings.hyde_enabled and self.hyde.should_apply(query, "all"):
            t0 = time.perf_counter()
            hyde_doc = await self.hyde.generate(query)
            search_query = hyde_doc
            trace.append(PipelineStep(
                name="hyde",
                passed=True,
                duration_ms=_elapsed_ms(t0),
                detail={"generated_length": len(hyde_doc)},
            ))

        # 2. 모드별 검색 실행
        mode = settings.search_mode
        documents: list[SearchResult] = []

        if mode == "vector":
            documents, step = await self._vector_search(search_query, settings)
            trace.append(step)

        elif mode == "keyword":
            documents, step = await self._keyword_search(query, settings)
            trace.append(step)

        else:  # hybrid
            vec_docs, vec_step, kw_docs, kw_step = await self._hybrid_search(
                search_query, query, settings,
            )
            trace.append(vec_step)
            trace.append(kw_step)

            # 3. RRF 결합
            t0 = time.perf_counter()
            documents = self.rrf.combine(
                vec_docs, kw_docs,
                k=settings.rrf_constant,
                vector_weight=settings.vector_weight,
                keyword_weight=settings.keyword_weight,
            )
            trace.append(PipelineStep(
                name="rrf_fusion",
                passed=True,
                duration_ms=_elapsed_ms(t0),
                results_count=len(documents),
            ))

        # 4. 리랭킹 (선택적)
        if settings.reranking_enabled:
            t0 = time.perf_counter()
            documents = await self.reranker.rerank(
                query, documents, top_k=settings.reranker_top_k,
            )
            trace.append(PipelineStep(
                name="reranking",
                passed=True,
                duration_ms=_elapsed_ms(t0),
                results_count=len(documents),
            ))

        # 5. 답변 생성 (선택적)
        answer: str | None = None
        if generate_answer:
            t0 = time.perf_counter()
            prompt = build_prompt(query, documents)
            answer = await self.llm.generate(prompt, system_prompt=SYSTEM_PROMPT)
            trace.append(PipelineStep(
                name="generation",
                passed=True,
                duration_ms=_elapsed_ms(t0),
            ))

        return SearchPipelineResult(
            documents=documents,
            answer=answer,
            trace=trace,
        )

    # ------------------------------------------------------------------
    # 내부 검색 메서드
    # ------------------------------------------------------------------

    async def _vector_search(
        self, search_query: str, settings: RAGSettings,
    ) -> tuple[list[SearchResult], PipelineStep]:
        """벡터 검색 실행."""
        t0 = time.perf_counter()
        query_embedding = await self.embedder.embed_query(search_query)
        results = await self.vector_engine.search(
            query_embedding, top_k=settings.retriever_top_k,
        )
        step = PipelineStep(
            name="vector_search",
            passed=True,
            duration_ms=_elapsed_ms(t0),
            results_count=len(results),
        )
        return results, step

    async def _keyword_search(
        self, query: str, settings: RAGSettings,
    ) -> tuple[list[SearchResult], PipelineStep]:
        """키워드 검색 실행."""
        t0 = time.perf_counter()
        results = await self.keyword_engine.search(
            query, top_k=settings.retriever_top_k,
        )
        step = PipelineStep(
            name="keyword_search",
            passed=True,
            duration_ms=_elapsed_ms(t0),
            results_count=len(results),
        )
        return results, step

    async def _hybrid_search(
        self,
        search_query: str,
        original_query: str,
        settings: RAGSettings,
    ) -> tuple[list[SearchResult], PipelineStep, list[SearchResult], PipelineStep]:
        """벡터 + 키워드 병렬 검색."""
        t0_vec = time.perf_counter()
        t0_kw = time.perf_counter()

        query_embedding = await self.embedder.embed_query(search_query)

        vec_task = self.vector_engine.search(
            query_embedding, top_k=settings.retriever_top_k,
        )
        kw_task = self.keyword_engine.search(
            original_query, top_k=settings.retriever_top_k,
        )

        vec_results, kw_results = await asyncio.gather(vec_task, kw_task)

        elapsed = _elapsed_ms(t0_vec)
        vec_step = PipelineStep(
            name="vector_search", passed=True,
            duration_ms=elapsed, results_count=len(vec_results),
        )
        kw_step = PipelineStep(
            name="keyword_search", passed=True,
            duration_ms=elapsed, results_count=len(kw_results),
        )

        return vec_results, vec_step, kw_results, kw_step


def _elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 2)
