"""Cascading + Query Expansion 검색 통합 테스트."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.config import RAGSettings
from app.models.schemas import SearchResult

UUID_A = uuid.UUID("00000000-0000-0000-0000-000000000001")
UUID_B = uuid.UUID("00000000-0000-0000-0000-000000000002")
UUID_C = uuid.UUID("00000000-0000-0000-0000-000000000003")
DOC_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a1")


def _make_result(chunk_id: uuid.UUID, score: float, content: str = "테스트") -> SearchResult:
    return SearchResult(
        chunk_id=chunk_id, document_id=DOC_ID, content=content, score=score,
    )


@pytest.fixture
def high_score_results():
    """BM25가 충분한 결과를 반환하는 경우."""
    return [_make_result(UUID_A, 8.0, "좋은 결과 A"), _make_result(UUID_B, 5.0, "좋은 결과 B"), _make_result(UUID_C, 3.5, "좋은 결과 C")]


@pytest.fixture
def low_score_results():
    """BM25가 불충분한 결과를 반환하는 경우."""
    return [_make_result(UUID_A, 0.5, "약한 결과 A"), _make_result(UUID_B, 0.3, "약한 결과 B")]


@pytest.fixture
def mock_embedder():
    m = AsyncMock()
    m.embed_query.return_value = [0.1] * 1536
    return m


@pytest.fixture
def mock_vector_engine():
    m = AsyncMock()
    m.search.return_value = [_make_result(UUID_C, 0.7, "벡터 결과 C")]
    return m


@pytest.fixture
def mock_keyword_engine_high(high_score_results):
    m = AsyncMock()
    m.search.return_value = high_score_results
    return m


@pytest.fixture
def mock_keyword_engine_low(low_score_results):
    m = AsyncMock()
    m.search.return_value = low_score_results
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
def mock_query_expander():
    from app.services.search.query_expander import ExpandedQuery, QueryExpander

    m = AsyncMock(spec=QueryExpander)
    m.expand.return_value = ExpandedQuery(
        original_query="테스트 쿼리",
        hypothetical_answer="가상 답변입니다.",
        expanded_keywords=["키워드1", "키워드2"],
        expanded_query="테스트 쿼리 키워드1 키워드2",
    )
    return m


@pytest.fixture
def cascading_settings() -> RAGSettings:
    return RAGSettings(
        search_mode="cascading",
        reranking_enabled=True,
        hyde_enabled=False,
        retriever_top_k=20,
        reranker_top_k=5,
        cascading_bm25_threshold=3.0,
        cascading_min_qualifying_docs=3,
        cascading_min_doc_score=1.0,
        cascading_fallback_vector_weight=0.3,
        cascading_fallback_keyword_weight=0.7,
        query_expansion_enabled=True,
        query_expansion_max_keywords=10,
        # 가드레일 비활성화
        injection_detection_enabled=False,
        pii_detection_enabled=False,
        hallucination_detection_enabled=False,
        retrieval_quality_gate_enabled=False,
        faithfulness_enabled=False,
    )


def _make_orchestrator(
    mock_embedder, mock_vector_engine, mock_keyword_engine,
    mock_reranker, mock_hyde, mock_llm, mock_query_expander,
):
    from app.services.search.hybrid import HybridSearchOrchestrator

    return HybridSearchOrchestrator(
        embedder=mock_embedder,
        vector_engine=mock_vector_engine,
        keyword_engine=mock_keyword_engine,
        reranker=mock_reranker,
        hyde_generator=mock_hyde,
        llm=mock_llm,
        query_expander=mock_query_expander,
    )


class TestCascadingBM25Sufficient:
    """BM25 결과가 충분할 때 — 벡터 검색/확장 없이 바로 반환."""

    @pytest.mark.asyncio
    async def test_bm25_sufficient_no_fallback(
        self, mock_embedder, mock_vector_engine, mock_keyword_engine_high,
        mock_reranker, mock_hyde, mock_llm, mock_query_expander, cascading_settings,
    ):
        orchestrator = _make_orchestrator(
            mock_embedder, mock_vector_engine, mock_keyword_engine_high,
            mock_reranker, mock_hyde, mock_llm, mock_query_expander,
        )
        result = await orchestrator.search("테스트 쿼리", cascading_settings)

        assert result.documents is not None
        assert len(result.documents) > 0
        # BM25만 호출, 벡터 미호출
        mock_keyword_engine_high.search.assert_called_once()
        mock_vector_engine.search.assert_not_called()
        # 쿼리 확장 미호출
        mock_query_expander.expand.assert_not_called()

    @pytest.mark.asyncio
    async def test_bm25_sufficient_trace(
        self, mock_embedder, mock_vector_engine, mock_keyword_engine_high,
        mock_reranker, mock_hyde, mock_llm, mock_query_expander, cascading_settings,
    ):
        orchestrator = _make_orchestrator(
            mock_embedder, mock_vector_engine, mock_keyword_engine_high,
            mock_reranker, mock_hyde, mock_llm, mock_query_expander,
        )
        result = await orchestrator.search("테스트 쿼리", cascading_settings)

        trace_names = [step.name for step in result.trace]
        assert "keyword_search" in trace_names
        assert "cascading_eval_stage1" in trace_names
        # 확장/폴백 단계 없음
        assert "query_expansion" not in trace_names
        assert "cascading_vector_fallback" not in trace_names


class TestCascadingQueryExpansion:
    """BM25 불충분 → 쿼리 확장 → ES 재검색."""

    @pytest.mark.asyncio
    async def test_bm25_insufficient_triggers_expansion(
        self, mock_embedder, mock_vector_engine, mock_keyword_engine_low,
        mock_reranker, mock_hyde, mock_llm, mock_query_expander, cascading_settings,
    ):
        # 확장 후 재검색 결과는 충분하게 설정
        expanded_results = [
            _make_result(UUID_A, 6.0, "확장 결과 A"),
            _make_result(UUID_B, 4.0, "확장 결과 B"),
            _make_result(UUID_C, 2.0, "확장 결과 C"),
        ]
        call_count = 0

        async def keyword_side_effect(query, top_k=20, doc_id=None):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [_make_result(UUID_A, 0.5), _make_result(UUID_B, 0.3)]
            return expanded_results

        mock_keyword_engine_low.search.side_effect = keyword_side_effect

        orchestrator = _make_orchestrator(
            mock_embedder, mock_vector_engine, mock_keyword_engine_low,
            mock_reranker, mock_hyde, mock_llm, mock_query_expander,
        )
        result = await orchestrator.search("테스트 쿼리", cascading_settings)

        # 쿼리 확장이 호출됨
        mock_query_expander.expand.assert_called_once()
        # 키워드 검색이 2번 호출됨 (원본 + 확장)
        assert mock_keyword_engine_low.search.call_count == 2
        # 벡터 폴백 미호출
        mock_vector_engine.search.assert_not_called()

        trace_names = [step.name for step in result.trace]
        assert "cascading_eval_stage1" in trace_names
        assert "query_expansion" in trace_names
        assert "keyword_search_expanded" in trace_names
        assert "cascading_eval_stage2" in trace_names


class TestCascadingVectorFallback:
    """BM25 + 확장 모두 불충분 → 벡터 폴백."""

    @pytest.mark.asyncio
    async def test_all_stages_to_vector_fallback(
        self, mock_embedder, mock_vector_engine, mock_keyword_engine_low,
        mock_reranker, mock_hyde, mock_llm, mock_query_expander, cascading_settings,
    ):
        orchestrator = _make_orchestrator(
            mock_embedder, mock_vector_engine, mock_keyword_engine_low,
            mock_reranker, mock_hyde, mock_llm, mock_query_expander,
        )
        result = await orchestrator.search("테스트 쿼리", cascading_settings)

        # 벡터 검색이 호출됨
        mock_vector_engine.search.assert_called_once()
        # 쿼리 확장도 호출됨
        mock_query_expander.expand.assert_called_once()

        trace_names = [step.name for step in result.trace]
        assert "cascading_vector_fallback" in trace_names

    @pytest.mark.asyncio
    async def test_expansion_disabled_skips_to_vector(
        self, mock_embedder, mock_vector_engine, mock_keyword_engine_low,
        mock_reranker, mock_hyde, mock_llm, mock_query_expander, cascading_settings,
    ):
        cascading_settings.query_expansion_enabled = False

        orchestrator = _make_orchestrator(
            mock_embedder, mock_vector_engine, mock_keyword_engine_low,
            mock_reranker, mock_hyde, mock_llm, mock_query_expander,
        )
        result = await orchestrator.search("테스트 쿼리", cascading_settings)

        # 쿼리 확장 미호출, 바로 벡터 폴백
        mock_query_expander.expand.assert_not_called()
        mock_vector_engine.search.assert_called_once()

        trace_names = [step.name for step in result.trace]
        assert "query_expansion" not in trace_names
        assert "cascading_vector_fallback" in trace_names


class TestCascadingWithReranking:
    """Cascading 결과도 리랭커를 거쳐야 한다."""

    @pytest.mark.asyncio
    async def test_cascading_with_reranking(
        self, mock_embedder, mock_vector_engine, mock_keyword_engine_high,
        mock_reranker, mock_hyde, mock_llm, mock_query_expander, cascading_settings,
    ):
        orchestrator = _make_orchestrator(
            mock_embedder, mock_vector_engine, mock_keyword_engine_high,
            mock_reranker, mock_hyde, mock_llm, mock_query_expander,
        )
        result = await orchestrator.search("테스트 쿼리", cascading_settings)

        mock_reranker.rerank.assert_called_once()
        trace_names = [step.name for step in result.trace]
        assert "reranking" in trace_names
