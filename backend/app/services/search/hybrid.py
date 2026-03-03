"""하이브리드 검색 오케스트레이터.

전체 검색 파이프라인 조립:
  [입력 가드레일] → 질문 분류 → 멀티쿼리 생성 → HyDE(선택) → 병렬 검색
  → RRF 결합 → 리랭킹(선택) → [출력 가드레일: PII] → 답변 생성 분기(규정형/설명형)
  → [숫자 검증] → [출력 가드레일: 충실도/할루시네이션]
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from app.config import RAGSettings
from app.exceptions import GuardrailViolation
from app.models.schemas import PipelineStep, SearchPipelineResult, SearchResult
from app.services.embedding.base import EmbeddingProvider
from app.services.generation.base import LLMProvider
from app.services.generation.evidence_extractor import EvidenceExtractor
from app.services.generation.prompts import SYSTEM_PROMPT, build_prompt
from app.services.guardrails.faithfulness import FaithfulnessChecker
from app.services.guardrails.hallucination import HallucinationDetector
from app.services.guardrails.injection import PromptInjectionDetector
from app.services.guardrails.numeric_verifier import NumericVerifier
from app.services.guardrails.pii import KoreanPIIDetector
from app.services.guardrails.retrieval_gate import RetrievalQualityGate
from app.services.hyde.generator import HyDEGenerator
from app.services.reranking.base import Reranker
from app.services.search.cascading_evaluator import CascadingQualityEvaluator
from app.services.search.document_scope import DocumentScopeSelector
from app.services.search.multi_query import MultiQueryGenerator
from app.services.search.query_expander import QueryExpander
from app.services.search.question_classifier import QuestionClassifier
from app.services.search.rrf import RRFCombiner

if TYPE_CHECKING:
    from app.monitoring.langfuse import LangfuseMonitor

logger = logging.getLogger(__name__)


class HybridSearchOrchestrator:
    """하이브리드 검색 오케스트레이터.

    벡터 검색, 키워드 검색, RRF 결합, 리랭킹, HyDE, 멀티쿼리,
    질문 분류, 정확 인용 모드, 숫자 검증, 답변 생성,
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
        langfuse_monitor: LangfuseMonitor | None = None,
        query_expander: QueryExpander | None = None,
        multi_query_generator: MultiQueryGenerator | None = None,
        question_classifier: QuestionClassifier | None = None,
        evidence_extractor: EvidenceExtractor | None = None,
        numeric_verifier: NumericVerifier | None = None,
    ) -> None:
        self.embedder = embedder
        self.vector_engine = vector_engine
        self.keyword_engine = keyword_engine
        self.reranker = reranker
        self.hyde = hyde_generator
        self.llm = llm
        self.rrf = RRFCombiner()
        self.langfuse = langfuse_monitor
        self.query_expander = query_expander or QueryExpander(llm=llm)

        # Phase 11: 멀티쿼리, 질문 분류, 근거 추출, 숫자 검증
        self.multi_query_generator = multi_query_generator or MultiQueryGenerator(llm=llm)
        self.question_classifier = question_classifier or QuestionClassifier()
        self.evidence_extractor = evidence_extractor or EvidenceExtractor(llm=llm)
        self.numeric_verifier = numeric_verifier or NumericVerifier()

        # 가드레일 (LLM이 필요한 것은 llm 공유)
        self.injection_detector = PromptInjectionDetector(llm=llm)
        self.pii_detector = KoreanPIIDetector(llm=None)  # PII LLM 검증은 별도 설정
        self.hallucination_detector = HallucinationDetector(llm=llm)
        self.faithfulness_checker = FaithfulnessChecker(llm=llm)
        self.retrieval_gate = RetrievalQualityGate()
        self.document_scope = DocumentScopeSelector()

    async def search(
        self,
        query: str,
        settings: RAGSettings,
        generate_answer: bool = True,
    ) -> SearchPipelineResult:
        """전체 검색 파이프라인을 실행한다."""
        trace: list[PipelineStep] = []

        # Langfuse 트레이싱
        lf_trace = self.langfuse.create_trace("rag-search", query) if self.langfuse else None

        # ── [입력 가드레일] 프롬프트 인젝션 검사 ──
        if settings.injection_detection_enabled:
            lf_span = self._lf_span(lf_trace, "guardrail-input")
            t0 = time.perf_counter()
            injection_result = await self.injection_detector.detect(query)
            passed = not injection_result.blocked
            trace.append(PipelineStep(
                name="guardrail_input",
                passed=passed,
                duration_ms=_elapsed_ms(t0),
                detail={"reason": injection_result.reason} if not passed else None,
            ))
            self._lf_end(lf_span, {"passed": passed})
            if injection_result.blocked:
                raise GuardrailViolation(
                    injection_result.reason or "프롬프트 인젝션이 감지되었습니다."
                )

        # ── [Phase 11] 질문 유형 분류 ──
        question_type = self.question_classifier.classify(query)
        trace.append(PipelineStep(
            name="question_classification",
            passed=True,
            duration_ms=0.0,
            detail={
                "category": question_type.category,
                "indicators": question_type.indicators,
            },
        ))

        # ── [Phase 11] 멀티쿼리 생성 ──
        if settings.multi_query_enabled:
            lf_span = self._lf_span(lf_trace, "multi-query")
            t0 = time.perf_counter()
            multi_result = await self.multi_query_generator.generate(
                query, count=settings.multi_query_count,
            )
            queries = multi_result.variant_queries
            trace.append(PipelineStep(
                name="multi_query",
                passed=True,
                duration_ms=_elapsed_ms(t0),
                detail={"variants": queries},
            ))
            self._lf_end(lf_span, {"variants": queries})
        else:
            queries = [query]

        # ── 1. HyDE (선택적) — 원문 쿼리에만 적용 ──
        search_query = query
        if settings.hyde_enabled and self.hyde.should_apply(query, "all"):
            lf_span = self._lf_span(lf_trace, "hyde")
            t0 = time.perf_counter()
            hyde_doc = await self.hyde.generate(query)
            search_query = hyde_doc
            trace.append(PipelineStep(
                name="hyde",
                passed=True,
                duration_ms=_elapsed_ms(t0),
                detail={"generated_length": len(hyde_doc)},
            ))
            self._lf_end(lf_span, {"generated_doc": hyde_doc[:200]})

        # ── 2. 모드별 검색 실행 × 멀티쿼리 (병렬) ──
        mode = settings.search_mode

        lf_search_span = self._lf_span(lf_trace, "hybrid-search")

        search_tasks = []
        for q in queries:
            if q == query:
                # 원문: 기존 파이프라인 (HyDE 적용된 search_query 사용)
                search_tasks.append(
                    self._search_single(search_query, query, settings, mode, trace),
                )
            else:
                # 변형: 벡터+키워드 직접 검색 (HyDE/Cascading 생략)
                search_tasks.append(
                    self._search_variant(q, settings),
                )

        all_results = await asyncio.gather(*search_tasks)
        # 원문 검색의 trace는 _search_single에서 직접 추가됨
        # all_results에서 문서 합집합 생성
        all_documents: list[SearchResult] = []
        for result in all_results:
            all_documents.extend(result)

        # ── 결과 합집합 + 중복 제거 ──
        documents = self._deduplicate_results(all_documents)

        self._lf_end(lf_search_span, {"count": len(documents)})

        # ── 3.5. 문서 스코프 선택 (리랭킹 전) ──
        if settings.document_scope_enabled and len(documents) > 0:
            self.document_scope.top_n = settings.document_scope_top_n
            before_count = len(documents)
            documents = self.document_scope.select(documents)
            if len(documents) < before_count:
                trace.append(PipelineStep(
                    name="document_scope",
                    passed=True,
                    duration_ms=0.0,
                    detail={
                        "before": before_count,
                        "after": len(documents),
                        "top_n": settings.document_scope_top_n,
                    },
                ))

        # ── 4. 리랭킹 (선택적) — 전체 합집합에 대해 1회 ──
        if settings.reranking_enabled:
            lf_span = self._lf_span(lf_trace, "reranking")
            t0 = time.perf_counter()
            documents = await self.reranker.rerank(
                query, documents, top_k=settings.reranker_top_k,
                score_mode=settings.reranker_score_mode,
                alpha=settings.reranker_alpha,
            )
            trace.append(PipelineStep(
                name="reranking",
                passed=True,
                duration_ms=_elapsed_ms(t0),
                results_count=len(documents),
            ))
            self._lf_end(lf_span, {"count": len(documents)})

        # ── [검색 품질 게이트] 점수 기반 품질 평가 + soft_fail 근거 추출 ──
        gate_soft_failed = False
        if settings.retrieval_quality_gate_enabled:
            gate_settings = settings.guardrails.retrieval_gate
            self.retrieval_gate.min_top_score = gate_settings.min_top_score
            self.retrieval_gate.min_doc_count = gate_settings.min_doc_count
            self.retrieval_gate.min_doc_score = gate_settings.min_doc_score
            self.retrieval_gate.soft_mode = gate_settings.soft_mode

            t0 = time.perf_counter()
            gate_result = self.retrieval_gate.evaluate(documents)
            trace.append(PipelineStep(
                name="retrieval_gate",
                passed=gate_result.passed,
                duration_ms=_elapsed_ms(t0),
                results_count=gate_result.qualifying_count,
                detail={
                    "top_score": gate_result.top_score,
                    "reason": gate_result.reason,
                    "soft_fail": gate_result.soft_fail,
                } if not gate_result.passed else {
                    "top_score": gate_result.top_score,
                },
            ))
            if not gate_result.passed:
                if gate_result.soft_fail and documents:
                    # soft_fail: 근거 추출을 시도하여 답변 가능 여부 판정
                    gate_soft_failed = True
                else:
                    return SearchPipelineResult(
                        documents=documents,
                        answer=gate_settings.not_found_message,
                        trace=trace,
                    )

        # ── [출력 가드레일 1] PII 탐지/마스킹 ──
        if settings.pii_detection_enabled:
            lf_span = self._lf_span(lf_trace, "guardrail-pii")
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
            self._lf_end(lf_span, {"pii_found": pii_found})

        # ── 5. 답변 생성 (선택적) — 규정형/추출형/설명형 분기 ──
        answer: str | None = None
        if generate_answer:
            lf_gen = self._lf_generation(
                lf_trace, "answer-generation",
                settings.llm_model,
                {"query": query, "doc_count": len(documents)},
            )
            t0 = time.perf_counter()

            # soft_fail이면 근거 추출로 답변 가능 여부 판정
            if gate_soft_failed:
                evidence_result = await self.evidence_extractor.extract_and_answer(
                    query, documents,
                )
                if (
                    evidence_result is not None
                    and evidence_result.evidence_sentences
                ):
                    answer = evidence_result.answer
                    trace.append(PipelineStep(
                        name="evidence_extraction",
                        passed=True,
                        duration_ms=_elapsed_ms(t0),
                        detail={
                            "evidence_count": len(evidence_result.evidence_sentences),
                            "gate_rescue": True,
                        },
                    ))
                else:
                    # 근거 없음 → 최종 차단
                    gate_settings = settings.guardrails.retrieval_gate
                    self._lf_end(lf_gen, None)
                    return SearchPipelineResult(
                        documents=documents,
                        answer=gate_settings.not_found_message,
                        trace=trace,
                    )
            elif (
                settings.exact_citation_enabled
                and question_type.category == "regulatory"
            ):
                # 규정형: CoT 기반 근거 추출 + 답변
                evidence_result = await self.evidence_extractor.extract_and_answer(
                    query, documents,
                )
                if evidence_result is not None:
                    answer = evidence_result.answer
                    trace.append(PipelineStep(
                        name="evidence_extraction",
                        passed=True,
                        duration_ms=_elapsed_ms(t0),
                        detail={
                            "evidence_count": len(evidence_result.evidence_sentences),
                        },
                    ))
                else:
                    # 폴백: 기존 생성 프롬프트
                    prompt = build_prompt(query, documents)
                    answer = await self.llm.generate(
                        prompt, system_prompt=SYSTEM_PROMPT,
                    )
                    trace.append(PipelineStep(
                        name="generation",
                        passed=True,
                        duration_ms=_elapsed_ms(t0),
                    ))
            elif question_type.category == "extraction":
                # 추출형: 단답 추출 모드
                evidence_result = await self.evidence_extractor.extract_short_answer(
                    query, documents,
                )
                if evidence_result is not None:
                    answer = evidence_result.answer
                    trace.append(PipelineStep(
                        name="evidence_extraction",
                        passed=True,
                        duration_ms=_elapsed_ms(t0),
                        detail={
                            "evidence_count": len(evidence_result.evidence_sentences),
                            "mode": "extraction",
                        },
                    ))
                else:
                    prompt = build_prompt(query, documents)
                    answer = await self.llm.generate(
                        prompt, system_prompt=SYSTEM_PROMPT,
                    )
                    trace.append(PipelineStep(
                        name="generation",
                        passed=True,
                        duration_ms=_elapsed_ms(t0),
                    ))
            else:
                # 설명형: 기존 생성 프롬프트
                prompt = build_prompt(query, documents)
                answer = await self.llm.generate(
                    prompt, system_prompt=SYSTEM_PROMPT,
                )
                trace.append(PipelineStep(
                    name="generation",
                    passed=True,
                    duration_ms=_elapsed_ms(t0),
                ))

            self._lf_end(lf_gen, answer)

        # ── [Phase 11] 숫자 검증 가드레일 ──
        if settings.numeric_verification_enabled and answer is not None:
            t0 = time.perf_counter()
            verification = self.numeric_verifier.verify(
                answer, [d.content for d in documents],
            )
            trace.append(PipelineStep(
                name="numeric_verification",
                passed=verification.passed,
                duration_ms=_elapsed_ms(t0),
                detail={
                    "total_numbers": verification.total_numbers_found,
                    "ungrounded": verification.ungrounded_numbers,
                },
            ))
            if not verification.passed:
                logger.warning(
                    "숫자 검증 실패 — 근거 없는 수치: %s",
                    verification.ungrounded_numbers,
                )

        # ── [출력 가드레일 2] 충실도 검증 ──
        if settings.faithfulness_enabled and answer is not None:
            faith_settings = settings.guardrails.faithfulness
            self.faithfulness_checker.threshold = faith_settings.threshold

            lf_span = self._lf_span(lf_trace, "guardrail-faithfulness")
            t0 = time.perf_counter()
            doc_contents = [d.content for d in documents]
            faith_result = await self.faithfulness_checker.verify(answer, doc_contents)
            passed = faith_result.verdict == "FAITHFUL"
            trace.append(PipelineStep(
                name="guardrail_faithfulness",
                passed=passed,
                duration_ms=_elapsed_ms(t0),
                detail={"faithfulness_score": faith_result.faithfulness_score},
            ))
            self._lf_end(lf_span, {"faithfulness_score": faith_result.faithfulness_score})
            if not passed:
                answer = self.faithfulness_checker.handle_result(
                    answer, faith_result, action=faith_settings.action,
                )

        # ── [출력 가드레일 3] 할루시네이션 검증 ──
        if settings.hallucination_detection_enabled and answer is not None:
            lf_span = self._lf_span(lf_trace, "guardrail-hallucination")
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
            self._lf_end(lf_span, {"grounded_ratio": hal_result.grounded_ratio})
            if hal_result.grounded_ratio is not None and lf_trace:
                self.langfuse.score(
                    getattr(lf_trace, "id", ""), "hallucination", hal_result.grounded_ratio,
                )
            if not passed:
                answer = self.hallucination_detector.handle_result(
                    answer, hal_result, action="warn",
                )

        # 트레이스 완료
        if lf_trace:
            lf_trace.update(output=answer)

        return SearchPipelineResult(
            documents=documents,
            answer=answer,
            trace=trace,
        )

    # ------------------------------------------------------------------
    # Langfuse 헬퍼
    # ------------------------------------------------------------------

    def _lf_span(self, lf_trace, name: str):
        if not self.langfuse or not lf_trace:
            return None
        return self.langfuse.create_span(lf_trace, name)

    def _lf_generation(self, lf_trace, name: str, model: str, input: dict):
        if not self.langfuse or not lf_trace:
            return None
        return self.langfuse.create_generation(lf_trace, name, model, input)

    @staticmethod
    def _lf_end(obj, output=None):
        if obj is not None:
            obj.end(output=output)

    # ------------------------------------------------------------------
    # 내부 검색 메서드
    # ------------------------------------------------------------------

    async def _search_single(
        self,
        search_query: str,
        original_query: str,
        settings: RAGSettings,
        mode: str,
        trace: list[PipelineStep],
    ) -> list[SearchResult]:
        """단일 쿼리에 대해 모드별 검색을 실행한다 (원문 전용)."""
        if mode == "vector":
            docs, step = await self._vector_search(search_query, settings)
            trace.append(step)
            return docs

        elif mode == "keyword":
            docs, step = await self._keyword_search(original_query, settings)
            trace.append(step)
            return docs

        elif mode == "cascading":
            docs, cascading_steps = await self._cascading_search(
                original_query, settings,
            )
            trace.extend(cascading_steps)
            return docs

        else:  # hybrid
            vec_docs, vec_step, kw_docs, kw_step = await self._hybrid_search(
                search_query, original_query, settings,
            )
            trace.append(vec_step)
            trace.append(kw_step)

            t0 = time.perf_counter()
            docs = self.rrf.combine(
                vec_docs, kw_docs,
                k=settings.rrf_constant,
                vector_weight=settings.vector_weight,
                keyword_weight=settings.keyword_weight,
            )
            trace.append(PipelineStep(
                name="rrf_fusion",
                passed=True,
                duration_ms=_elapsed_ms(t0),
                results_count=len(docs),
            ))
            return docs

    async def _search_variant(
        self,
        query: str,
        settings: RAGSettings,
    ) -> list[SearchResult]:
        """변형 쿼리 전용 검색 (HyDE/Cascading 생략, 벡터+키워드 직접)."""
        vec_docs, _, kw_docs, _ = await self._hybrid_search(
            query, query, settings,
        )
        return self.rrf.combine(
            vec_docs, kw_docs,
            k=settings.rrf_constant,
            vector_weight=settings.vector_weight,
            keyword_weight=settings.keyword_weight,
        )

    @staticmethod
    def _deduplicate_results(
        documents: list[SearchResult],
    ) -> list[SearchResult]:
        """chunk_id 기반 중복 제거, 최고 점수 유지."""
        seen: dict[str, SearchResult] = {}
        for doc in documents:
            key = str(doc.chunk_id)
            if key not in seen or doc.score > seen[key].score:
                seen[key] = doc
        # 점수 내림차순 정렬
        return sorted(seen.values(), key=lambda d: d.score, reverse=True)

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

    async def _cascading_search(
        self,
        query: str,
        settings: RAGSettings,
    ) -> tuple[list[SearchResult], list[PipelineStep]]:
        """Cascading + Query Expansion 검색.

        1. BM25 검색 → 품질 평가
        2. 불충분 → HyDE 키워드 확장 → ES 재검색 → 품질 재평가
        3. 여전히 불충분 → 벡터 폴백 (비대칭 RRF)
        """
        steps: list[PipelineStep] = []
        evaluator = CascadingQualityEvaluator(
            threshold=settings.cascading_bm25_threshold,
            min_qualifying_docs=settings.cascading_min_qualifying_docs,
            min_doc_score=settings.cascading_min_doc_score,
        )

        # ── Stage 1: BM25 검색 ──
        kw_docs, kw_step = await self._keyword_search(query, settings)
        steps.append(kw_step)

        t0 = time.perf_counter()
        eval1 = evaluator.evaluate(kw_docs)
        steps.append(PipelineStep(
            name="cascading_eval_stage1",
            passed=eval1.sufficient,
            duration_ms=_elapsed_ms(t0),
            detail={"top_score": eval1.top_score, "qualifying": eval1.qualifying_count},
        ))

        if eval1.sufficient:
            return kw_docs, steps

        # ── Stage 2: Query Expansion (HyDE 키워드 확장) ──
        if settings.query_expansion_enabled:
            t0 = time.perf_counter()
            expanded = await self.query_expander.expand(
                query, max_keywords=settings.query_expansion_max_keywords,
            )
            steps.append(PipelineStep(
                name="query_expansion",
                passed=True,
                duration_ms=_elapsed_ms(t0),
                detail={"keywords": expanded.expanded_keywords},
            ))

            # 확장된 쿼리로 ES 재검색
            expanded_docs, expanded_step = await self._keyword_search(
                expanded.expanded_query, settings,
            )
            expanded_step = PipelineStep(
                name="keyword_search_expanded",
                passed=expanded_step.passed,
                duration_ms=expanded_step.duration_ms,
                results_count=expanded_step.results_count,
            )
            steps.append(expanded_step)

            t0 = time.perf_counter()
            eval2 = evaluator.evaluate(expanded_docs)
            steps.append(PipelineStep(
                name="cascading_eval_stage2",
                passed=eval2.sufficient,
                duration_ms=_elapsed_ms(t0),
                detail={"top_score": eval2.top_score, "qualifying": eval2.qualifying_count},
            ))

            if eval2.sufficient:
                return expanded_docs, steps

        # ── Stage 3: 벡터 폴백 (비대칭 RRF) ──
        vec_docs, vec_step, kw_docs2, kw_step2 = await self._hybrid_search(
            query, query, settings,
        )
        steps.append(vec_step)
        steps.append(kw_step2)

        t0 = time.perf_counter()
        documents = self.rrf.combine(
            vec_docs, kw_docs2,
            k=settings.rrf_constant,
            vector_weight=settings.cascading_fallback_vector_weight,
            keyword_weight=settings.cascading_fallback_keyword_weight,
        )
        steps.append(PipelineStep(
            name="cascading_vector_fallback",
            passed=True,
            duration_ms=_elapsed_ms(t0),
            results_count=len(documents),
        ))

        return documents, steps

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
