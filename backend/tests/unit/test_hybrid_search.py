"""Step 4.7 RED: 하이브리드 검색 오케스트레이터 단위 테스트."""
from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import RAGSettings
from app.models.schemas import SearchResult

# 테스트용 UUID
UUID_A = uuid.UUID("00000000-0000-0000-0000-000000000001")
UUID_B = uuid.UUID("00000000-0000-0000-0000-000000000002")
UUID_C = uuid.UUID("00000000-0000-0000-0000-000000000003")
DOC_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a1")


def _make_result(chunk_id: uuid.UUID, score: float, content: str = "test") -> SearchResult:
    return SearchResult(
        chunk_id=chunk_id,
        document_id=DOC_ID,
        content=content,
        score=score,
    )


@pytest.fixture
def vector_results() -> list[SearchResult]:
    return [_make_result(UUID_A, 0.9, "벡터 결과 A"), _make_result(UUID_B, 0.8, "벡터 결과 B")]


@pytest.fixture
def keyword_results() -> list[SearchResult]:
    return [_make_result(UUID_B, 5.5, "키워드 결과 B"), _make_result(UUID_C, 3.2, "키워드 결과 C")]


@pytest.fixture
def mock_embedder():
    m = AsyncMock()
    m.embed_query.return_value = [0.1] * 1536
    return m


@pytest.fixture
def mock_vector_engine(vector_results):
    m = AsyncMock()
    m.search.return_value = vector_results
    return m


@pytest.fixture
def mock_keyword_engine(keyword_results):
    m = AsyncMock()
    m.search.return_value = keyword_results
    return m


@pytest.fixture
def mock_reranker():
    m = AsyncMock()

    async def _rerank(query, documents, top_k=5):
        return documents[:top_k]

    m.rerank.side_effect = _rerank
    return m


@pytest.fixture
def mock_hyde():
    m = MagicMock()
    m.should_apply.return_value = False
    m.generate = AsyncMock(return_value="가상 문서 내용")
    return m


@pytest.fixture
def mock_llm():
    m = AsyncMock()
    m.generate.return_value = "이것은 생성된 답변입니다."
    return m


@pytest.fixture
def rag_settings() -> RAGSettings:
    return RAGSettings(
        search_mode="hybrid",
        reranking_enabled=True,
        hyde_enabled=False,
        retriever_top_k=20,
        reranker_top_k=5,
        rrf_constant=60,
        vector_weight=0.5,
        keyword_weight=0.5,
        # Phase 4 테스트에서는 가드레일 비활성화
        injection_detection_enabled=False,
        pii_detection_enabled=False,
        hallucination_detection_enabled=False,
        retrieval_quality_gate_enabled=False,
        faithfulness_enabled=False,
        # Phase 11: 기존 테스트 격리를 위해 비활성화
        multi_query_enabled=False,
        exact_citation_enabled=False,
        numeric_verification_enabled=False,
    )


@pytest.fixture
def orchestrator(
    mock_embedder, mock_vector_engine, mock_keyword_engine,
    mock_reranker, mock_hyde, mock_llm,
):
    from app.services.search.hybrid import HybridSearchOrchestrator

    return HybridSearchOrchestrator(
        embedder=mock_embedder,
        vector_engine=mock_vector_engine,
        keyword_engine=mock_keyword_engine,
        reranker=mock_reranker,
        hyde_generator=mock_hyde,
        llm=mock_llm,
    )


class TestHybridSearch:
    """하이브리드 모드 검색 테스트."""

    @pytest.mark.asyncio
    async def test_hybrid_search(self, orchestrator, rag_settings, mock_vector_engine, mock_keyword_engine):
        """하이브리드 검색: 벡터 + 키워드 양쪽 호출 후 결과 반환."""
        result = await orchestrator.search("테스트 쿼리", rag_settings)

        assert result.documents is not None
        assert len(result.documents) > 0
        mock_vector_engine.search.assert_called_once()
        mock_keyword_engine.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_hybrid_search_returns_answer(self, orchestrator, rag_settings, mock_llm):
        """답변 생성 포함 시 answer 필드가 채워진다."""
        result = await orchestrator.search("테스트 쿼리", rag_settings, generate_answer=True)

        assert result.answer is not None
        assert result.answer == "이것은 생성된 답변입니다."
        mock_llm.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_hybrid_search_no_answer(self, orchestrator, rag_settings, mock_llm):
        """generate_answer=False일 때 LLM 미호출."""
        result = await orchestrator.search("테스트 쿼리", rag_settings, generate_answer=False)

        assert result.answer is None
        mock_llm.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_hybrid_search_trace(self, orchestrator, rag_settings):
        """파이프라인 trace에 각 단계가 기록된다."""
        result = await orchestrator.search("테스트 쿼리", rag_settings)

        trace_names = [step.name for step in result.trace]
        assert "vector_search" in trace_names
        assert "keyword_search" in trace_names
        assert "rrf_fusion" in trace_names
        assert "reranking" in trace_names


class TestVectorOnlyMode:
    """벡터 전용 모드 테스트."""

    @pytest.mark.asyncio
    async def test_vector_only_mode(
        self, orchestrator, rag_settings, mock_vector_engine, mock_keyword_engine,
    ):
        """search_mode='vector'일 때 벡터 검색만 실행."""
        rag_settings.search_mode = "vector"

        result = await orchestrator.search("테스트 쿼리", rag_settings)

        assert result.documents is not None
        mock_vector_engine.search.assert_called_once()
        mock_keyword_engine.search.assert_not_called()


class TestKeywordOnlyMode:
    """키워드 전용 모드 테스트."""

    @pytest.mark.asyncio
    async def test_keyword_only_mode(
        self, orchestrator, rag_settings, mock_vector_engine, mock_keyword_engine,
    ):
        """search_mode='keyword'일 때 키워드 검색만 실행."""
        rag_settings.search_mode = "keyword"

        result = await orchestrator.search("테스트 쿼리", rag_settings)

        assert result.documents is not None
        mock_vector_engine.search.assert_not_called()
        mock_keyword_engine.search.assert_called_once()


class TestSearchWithHyDE:
    """HyDE 적용 테스트."""

    @pytest.mark.asyncio
    async def test_search_with_hyde(
        self, orchestrator, rag_settings, mock_hyde, mock_embedder,
    ):
        """HyDE 활성화 시 가상 문서 기반으로 임베딩."""
        rag_settings.hyde_enabled = True
        mock_hyde.should_apply.return_value = True

        result = await orchestrator.search("복잡한 질문입니다", rag_settings)

        mock_hyde.generate.assert_called_once_with("복잡한 질문입니다")
        # HyDE 적용 시 가상 문서로 임베딩
        mock_embedder.embed_query.assert_called_once_with("가상 문서 내용")

        trace_names = [step.name for step in result.trace]
        assert "hyde" in trace_names

    @pytest.mark.asyncio
    async def test_search_hyde_disabled(
        self, orchestrator, rag_settings, mock_hyde, mock_embedder,
    ):
        """HyDE 비활성화 시 원본 쿼리로 임베딩."""
        rag_settings.hyde_enabled = False

        result = await orchestrator.search("간단한 질문", rag_settings)

        mock_hyde.generate.assert_not_called()
        mock_embedder.embed_query.assert_called_once_with("간단한 질문")


class TestSearchWithReranking:
    """리랭킹 적용 테스트."""

    @pytest.mark.asyncio
    async def test_search_with_reranking(
        self, orchestrator, rag_settings, mock_reranker,
    ):
        """리랭킹 활성화 시 reranker 호출."""
        rag_settings.reranking_enabled = True

        result = await orchestrator.search("테스트 쿼리", rag_settings)

        mock_reranker.rerank.assert_called_once()
        trace_names = [step.name for step in result.trace]
        assert "reranking" in trace_names

    @pytest.mark.asyncio
    async def test_search_without_reranking(
        self, orchestrator, rag_settings, mock_reranker,
    ):
        """리랭킹 비활성화 시 reranker 미호출."""
        rag_settings.reranking_enabled = False

        result = await orchestrator.search("테스트 쿼리", rag_settings)

        mock_reranker.rerank.assert_not_called()
        trace_names = [step.name for step in result.trace]
        assert "reranking" not in trace_names


# ==========================================================
# Phase 11: 멀티쿼리 + 정확 인용 + 숫자 검증 통합 테스트
# ==========================================================

@pytest.fixture
def multi_query_settings() -> RAGSettings:
    """멀티쿼리/정확인용/숫자검증 활성 설정."""
    return RAGSettings(
        search_mode="hybrid",
        reranking_enabled=True,
        hyde_enabled=False,
        retriever_top_k=20,
        reranker_top_k=5,
        injection_detection_enabled=False,
        pii_detection_enabled=False,
        hallucination_detection_enabled=False,
        retrieval_quality_gate_enabled=False,
        faithfulness_enabled=False,
        # Phase 11 활성화
        multi_query_enabled=True,
        multi_query_count=4,
        exact_citation_enabled=True,
        numeric_verification_enabled=True,
    )


@pytest.fixture
def mq_orchestrator(
    mock_embedder, mock_vector_engine, mock_keyword_engine,
    mock_reranker, mock_hyde, mock_llm,
):
    """멀티쿼리 테스트용 오케스트레이터."""
    from app.services.search.hybrid import HybridSearchOrchestrator

    # mock_llm.generate의 기본 반환을 멀티쿼리 + 답변 양쪽에 대응
    mock_llm.generate.return_value = "이것은 생성된 답변입니다."

    return HybridSearchOrchestrator(
        embedder=mock_embedder,
        vector_engine=mock_vector_engine,
        keyword_engine=mock_keyword_engine,
        reranker=mock_reranker,
        hyde_generator=mock_hyde,
        llm=mock_llm,
    )


class TestMultiQueryIntegration:
    """멀티쿼리 통합 테스트."""

    @pytest.mark.asyncio
    async def test_multi_query_trace_recorded(
        self, mq_orchestrator, multi_query_settings,
    ):
        """멀티쿼리 활성화 시 trace에 multi_query 단계가 기록된다."""
        result = await mq_orchestrator.search("테스트 질문", multi_query_settings)

        trace_names = [step.name for step in result.trace]
        assert "multi_query" in trace_names
        assert "question_classification" in trace_names

    @pytest.mark.asyncio
    async def test_multi_query_disabled_no_trace(
        self, mq_orchestrator, multi_query_settings,
    ):
        """멀티쿼리 비활성화 시 multi_query trace가 없다."""
        multi_query_settings.multi_query_enabled = False
        result = await mq_orchestrator.search("테스트 질문", multi_query_settings)

        trace_names = [step.name for step in result.trace]
        assert "multi_query" not in trace_names

    @pytest.mark.asyncio
    async def test_multi_query_deduplicates_results(
        self, mq_orchestrator, multi_query_settings,
    ):
        """결과에 중복 chunk_id가 없다."""
        result = await mq_orchestrator.search("테스트 질문", multi_query_settings)

        chunk_ids = [str(d.chunk_id) for d in result.documents]
        assert len(chunk_ids) == len(set(chunk_ids))


class TestExactCitationIntegration:
    """정확 인용 모드 통합 테스트."""

    @pytest.mark.asyncio
    async def test_regulatory_question_uses_evidence(
        self, mq_orchestrator, multi_query_settings, mock_llm,
    ):
        """규정형 질문은 evidence_extraction trace가 기록된다."""
        # LLM 응답: 근거+답변 형식
        mock_llm.generate.return_value = (
            "[근거]\n반기별 1회 이상 실시\n\n[답변]\n반기별 1회 이상 실시해야 합니다."
        )

        result = await mq_orchestrator.search(
            "평가는 몇 회 실시해야 하나요?", multi_query_settings,
        )

        trace_names = [step.name for step in result.trace]
        assert "evidence_extraction" in trace_names

    @pytest.mark.asyncio
    async def test_explanatory_question_uses_standard(
        self, mq_orchestrator, multi_query_settings,
    ):
        """설명형 질문은 기존 generation trace가 기록된다."""
        result = await mq_orchestrator.search(
            "장기요양이란 무엇인가요?", multi_query_settings,
        )

        trace_names = [step.name for step in result.trace]
        assert "generation" in trace_names

    @pytest.mark.asyncio
    async def test_exact_citation_disabled_uses_standard(
        self, mq_orchestrator, multi_query_settings,
    ):
        """정확 인용 비활성 시 규정형 질문도 기존 생성 사용."""
        multi_query_settings.exact_citation_enabled = False

        result = await mq_orchestrator.search(
            "평가는 몇 회 실시해야 하나요?", multi_query_settings,
        )

        trace_names = [step.name for step in result.trace]
        assert "generation" in trace_names
        assert "evidence_extraction" not in trace_names


class TestNumericVerificationIntegration:
    """숫자 검증 통합 테스트."""

    @pytest.mark.asyncio
    async def test_numeric_verification_trace(
        self, mq_orchestrator, multi_query_settings,
    ):
        """숫자 검증 trace가 기록된다."""
        result = await mq_orchestrator.search(
            "장기요양이란 무엇인가요?", multi_query_settings,
        )

        trace_names = [step.name for step in result.trace]
        assert "numeric_verification" in trace_names

    @pytest.mark.asyncio
    async def test_numeric_verification_disabled(
        self, mq_orchestrator, multi_query_settings,
    ):
        """숫자 검증 비활성 시 trace 없음."""
        multi_query_settings.numeric_verification_enabled = False

        result = await mq_orchestrator.search(
            "장기요양이란 무엇인가요?", multi_query_settings,
        )

        trace_names = [step.name for step in result.trace]
        assert "numeric_verification" not in trace_names
