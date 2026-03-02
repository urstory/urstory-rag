"""Step 6.3 RED: 검색 파이프라인 Langfuse 트레이싱 테스트."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from app.config import RAGSettings
from app.models.schemas import SearchResult
from app.monitoring.langfuse import LangfuseMonitor


DOC_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a1")
UUID_A = uuid.UUID("00000000-0000-0000-0000-000000000001")
UUID_B = uuid.UUID("00000000-0000-0000-0000-000000000002")


def _make_result(chunk_id: uuid.UUID, score: float, content: str = "test") -> SearchResult:
    return SearchResult(
        chunk_id=chunk_id, document_id=DOC_ID, content=content, score=score,
    )


@pytest.fixture
def mock_langfuse_monitor():
    """활성화된 LangfuseMonitor mock."""
    m = MagicMock(spec=LangfuseMonitor)
    m.enabled = True

    mock_trace = MagicMock()
    mock_trace.id = "trace-123"
    m.create_trace.return_value = mock_trace

    mock_span = MagicMock()
    mock_trace.span.return_value = mock_span
    m.create_span.return_value = mock_span

    mock_gen = MagicMock()
    mock_trace.generation.return_value = mock_gen
    m.create_generation.return_value = mock_gen

    return m


@pytest.fixture
def rag_settings() -> RAGSettings:
    return RAGSettings(
        search_mode="hybrid",
        reranking_enabled=True,
        hyde_enabled=False,
        injection_detection_enabled=False,
        pii_detection_enabled=False,
        hallucination_detection_enabled=False,
        retrieval_quality_gate_enabled=False,
        faithfulness_enabled=False,
    )


@pytest.fixture
def orchestrator_with_tracing(mock_langfuse_monitor):
    from app.services.search.hybrid import HybridSearchOrchestrator

    mock_embedder = AsyncMock()
    mock_embedder.embed_query.return_value = [0.1] * 1536

    mock_vector = AsyncMock()
    mock_vector.search.return_value = [_make_result(UUID_A, 0.9)]

    mock_keyword = AsyncMock()
    mock_keyword.search.return_value = [_make_result(UUID_B, 5.0)]

    mock_reranker = AsyncMock()

    async def _rerank(query, documents, top_k=5):
        return documents[:top_k]

    mock_reranker.rerank.side_effect = _rerank

    mock_hyde = MagicMock()
    mock_hyde.should_apply.return_value = False

    mock_llm = AsyncMock()
    mock_llm.generate.return_value = "생성된 답변"

    return HybridSearchOrchestrator(
        embedder=mock_embedder,
        vector_engine=mock_vector,
        keyword_engine=mock_keyword,
        reranker=mock_reranker,
        hyde_generator=mock_hyde,
        llm=mock_llm,
        langfuse_monitor=mock_langfuse_monitor,
    )


class TestSearchTracing:
    """검색 파이프라인 Langfuse 트레이싱 테스트."""

    @pytest.mark.asyncio
    async def test_search_creates_trace(
        self, orchestrator_with_tracing, rag_settings, mock_langfuse_monitor,
    ):
        """검색 실행 시 Langfuse 트레이스가 생성된다."""
        await orchestrator_with_tracing.search("테스트 질문", rag_settings)
        mock_langfuse_monitor.create_trace.assert_called_once_with("rag-search", "테스트 질문")

    @pytest.mark.asyncio
    async def test_trace_has_search_spans(
        self, orchestrator_with_tracing, rag_settings, mock_langfuse_monitor,
    ):
        """검색 실행 시 hybrid-search span이 생성된다."""
        await orchestrator_with_tracing.search("테스트 질문", rag_settings)
        span_names = [
            c.kwargs.get("name", c.args[1] if len(c.args) > 1 else None)
            for c in mock_langfuse_monitor.create_span.call_args_list
        ]
        assert "hybrid-search" in span_names

    @pytest.mark.asyncio
    async def test_trace_has_reranking_span(
        self, orchestrator_with_tracing, rag_settings, mock_langfuse_monitor,
    ):
        """리랭킹 활성화 시 reranking span이 생성된다."""
        await orchestrator_with_tracing.search("테스트 질문", rag_settings)
        span_names = [
            c.kwargs.get("name", c.args[1] if len(c.args) > 1 else None)
            for c in mock_langfuse_monitor.create_span.call_args_list
        ]
        assert "reranking" in span_names

    @pytest.mark.asyncio
    async def test_trace_has_generation(
        self, orchestrator_with_tracing, rag_settings, mock_langfuse_monitor,
    ):
        """답변 생성 시 generation이 기록된다."""
        await orchestrator_with_tracing.search(
            "테스트 질문", rag_settings, generate_answer=True,
        )
        mock_langfuse_monitor.create_generation.assert_called_once()

    @pytest.mark.asyncio
    async def test_trace_update_with_output(
        self, orchestrator_with_tracing, rag_settings, mock_langfuse_monitor,
    ):
        """파이프라인 완료 시 트레이스에 output이 업데이트된다."""
        mock_trace = mock_langfuse_monitor.create_trace.return_value
        await orchestrator_with_tracing.search(
            "테스트 질문", rag_settings, generate_answer=True,
        )
        mock_trace.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_tracing_without_monitor(self, rag_settings):
        """langfuse_monitor 없이도 정상 동작한다."""
        from app.services.search.hybrid import HybridSearchOrchestrator

        mock_embedder = AsyncMock()
        mock_embedder.embed_query.return_value = [0.1] * 1536
        mock_vector = AsyncMock()
        mock_vector.search.return_value = [_make_result(UUID_A, 0.9)]
        mock_keyword = AsyncMock()
        mock_keyword.search.return_value = [_make_result(UUID_B, 5.0)]
        mock_reranker = AsyncMock()
        mock_reranker.rerank.side_effect = lambda q, d, top_k=5: d[:top_k]
        mock_hyde = MagicMock()
        mock_hyde.should_apply.return_value = False
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "답변"

        orch = HybridSearchOrchestrator(
            embedder=mock_embedder,
            vector_engine=mock_vector,
            keyword_engine=mock_keyword,
            reranker=mock_reranker,
            hyde_generator=mock_hyde,
            llm=mock_llm,
        )

        result = await orch.search("테스트", rag_settings)
        assert result.documents is not None
