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
    m.embed_query.return_value = [0.1] * 1024
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
