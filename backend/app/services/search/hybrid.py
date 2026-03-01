"""하이브리드 검색 오케스트레이터.

전체 검색 파이프라인 조립:
  [입력 가드레일] → HyDE(선택) → 임베딩 → 병렬 검색 → RRF 결합
  → 리랭킹(선택) → [출력 가드레일: PII] → 답변 생성(선택) → [출력 가드레일: 할루시네이션]
"""
from __future__ import annotations

import asyncio
import time

from app.config import RAGSettings
from app.exceptions import GuardrailViolation
from app.models.schemas import PipelineStep, SearchPipelineResult, SearchResult
from app.services.embedding.base import EmbeddingProvider
from app.services.generation.base import LLMProvider
from app.services.generation.prompts import SYSTEM_PROMPT, build_prompt
from app.services.guardrails.hallucination import HallucinationDetector
from app.services.guardrails.injection import PromptInjectionDetector
from app.services.guardrails.pii import KoreanPIIDetector
from app.services.hyde.generator import HyDEGenerator
from app.services.reranking.base import Reranker
from app.services.search.rrf import RRFCombiner


class HybridSearchOrchestrator:
    """하이브리드 검색 오케스트레이터.

    벡터 검색, 키워드 검색, RRF 결합, 리랭킹, HyDE, 답변 생성,
    가드레일(인젝션/PII/할루시네이션)을 설정에 따라 동적으로 조합하여 실행한다.
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

        # 가드레일 (LLM이 필요한 것은 llm 공유)
        self.injection_detector = PromptInjectionDetector(llm=llm)
        self.pii_detector = KoreanPIIDetector(llm=None)  # PII LLM 검증은 별도 설정
        self.hallucination_detector = HallucinationDetector(llm=llm)

    async def search(
        self,
        query: str,
        settings: RAGSettings,
        generate_answer: bool = True,
    ) -> SearchPipelineResult:
        """전체 검색 파이프라인을 실행한다."""
        trace: list[PipelineStep] = []

        # ── [입력 가드레일] 프롬프트 인젝션 검사 ──
        if settings.injection_detection_enabled:
            t0 = time.perf_counter()
            injection_result = await self.injection_detector.detect(query)
            passed = not injection_result.blocked
            trace.append(PipelineStep(
                name="guardrail_input",
                passed=passed,
                duration_ms=_elapsed_ms(t0),
                detail={"reason": injection_result.reason} if not passed else None,
            ))
            if injection_result.blocked:
                raise GuardrailViolation(
                    injection_result.reason or "프롬프트 인젝션이 감지되었습니다."
                )

        # ── 1. HyDE (선택적) ──
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

        # ── 2. 모드별 검색 실행 ──
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

        # ── 4. 리랭킹 (선택적) ──
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

        # ── [출력 가드레일 1] PII 탐지/마스킹 ──
        if settings.pii_detection_enabled:
            t0 = time.perf_counter()
            pii_found = False
            for doc in documents:
                pii_matches = await self.pii_detector.detect(
                    doc.content, llm_verification=False,
                )
                if pii_matches:
                    pii_found = True
                    doc.content = self.pii_detector.mask(doc.content, pii_matches)
            trace.append(PipelineStep(
                name="guardrail_pii",
                passed=True,
                duration_ms=_elapsed_ms(t0),
                detail={"pii_found": pii_found},
            ))

        # ── 5. 답변 생성 (선택적) ──
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

        # ── [출력 가드레일 2] 할루시네이션 검증 ──
        if settings.hallucination_detection_enabled and answer is not None:
            t0 = time.perf_counter()
            doc_contents = [d.content for d in documents]
            hal_result = await self.hallucination_detector.verify(answer, doc_contents)
            passed = hal_result.verdict == "PASS"
            trace.append(PipelineStep(
                name="guardrail_hallucination",
                passed=passed,
                duration_ms=_elapsed_ms(t0),
                detail={"grounded_ratio": hal_result.grounded_ratio},
            ))
            if not passed:
                answer = self.hallucination_detector.handle_result(
                    answer, hal_result, action="warn",
                )

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
