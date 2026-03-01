"""Step 4.10 RED: 검색 API 엔드포인트 단위 테스트."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.config import RAGSettings
from app.main import app
from app.api.search import get_orchestrator, get_search_settings_service
from app.models.schemas import PipelineStep, SearchPipelineResult, SearchResult

# 테스트용 데이터
DOC_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a1")
CHUNK_A = uuid.UUID("00000000-0000-0000-0000-000000000001")
CHUNK_B = uuid.UUID("00000000-0000-0000-0000-000000000002")


def _make_pipeline_result(with_trace: bool = False) -> SearchPipelineResult:
    docs = [
        SearchResult(chunk_id=CHUNK_A, document_id=DOC_ID, content="연차 신청은...", score=0.95),
        SearchResult(chunk_id=CHUNK_B, document_id=DOC_ID, content="신청 절차는...", score=0.85),
    ]
    trace = []
    if with_trace:
        trace = [
            PipelineStep(name="vector_search", passed=True, duration_ms=50.0, results_count=20),
            PipelineStep(name="keyword_search", passed=True, duration_ms=30.0, results_count=15),
            PipelineStep(name="rrf_fusion", passed=True, duration_ms=1.0, results_count=25),
            PipelineStep(name="reranking", passed=True, duration_ms=200.0, results_count=5),
            PipelineStep(name="generation", passed=True, duration_ms=1500.0),
        ]
    return SearchPipelineResult(
        documents=docs,
        answer="연차 신청은 인사시스템에서 진행합니다.",
        trace=trace,
    )


@pytest.fixture
def mock_orchestrator():
    m = AsyncMock()
    m.search.return_value = _make_pipeline_result(with_trace=True)
    return m


@pytest.fixture
def mock_settings_service():
    m = AsyncMock()
    m.get_settings.return_value = RAGSettings()
    return m


@pytest_asyncio.fixture
async def client(mock_orchestrator, mock_settings_service):
    """FastAPI TestClient with mocked dependencies via dependency_overrides."""
    app.dependency_overrides[get_orchestrator] = lambda: mock_orchestrator
    app.dependency_overrides[get_search_settings_service] = lambda: mock_settings_service

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


class TestSearchAPI:
    """POST /api/search 테스트."""

    @pytest.mark.asyncio
    async def test_search_api(self, client, mock_orchestrator):
        """검색 API 호출 후 answer + results 반환."""
        resp = await client.post("/api/search", json={"query": "연차 신청 방법"})

        assert resp.status_code == 200
        data = resp.json()
        assert "answer" in data
        assert "results" in data
        assert data["query"] == "연차 신청 방법"
        assert len(data["results"]) == 2
        mock_orchestrator.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_api_empty_query(self, client):
        """빈 쿼리도 처리 가능."""
        resp = await client.post("/api/search", json={"query": ""})
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_search_with_override(self, client, mock_orchestrator):
        """요청에서 설정 오버라이드 확인."""
        resp = await client.post("/api/search", json={
            "query": "테스트",
            "search_mode": "vector",
            "hyde_enabled": False,
            "reranking_enabled": False,
        })

        assert resp.status_code == 200
        # orchestrator.search가 호출될 때 오버라이드된 settings가 전달되었는지 확인
        call_args = mock_orchestrator.search.call_args
        settings_arg = call_args[0][1]  # 두 번째 positional arg = settings
        assert settings_arg.search_mode == "vector"
        assert settings_arg.hyde_enabled is False
        assert settings_arg.reranking_enabled is False


class TestDebugSearchAPI:
    """POST /api/search/debug 테스트."""

    @pytest.mark.asyncio
    async def test_search_debug_api(self, client, mock_orchestrator):
        """디버그 API에서 pipeline_trace 포함."""
        resp = await client.post("/api/search/debug", json={"query": "연차 신청 방법"})

        assert resp.status_code == 200
        data = resp.json()
        assert "pipeline_trace" in data
        assert len(data["pipeline_trace"]) > 0

        trace_names = [step["name"] for step in data["pipeline_trace"]]
        assert "vector_search" in trace_names
        assert "generation" in trace_names

    @pytest.mark.asyncio
    async def test_search_debug_has_answer(self, client):
        """디버그 API에도 answer가 포함된다."""
        resp = await client.post("/api/search/debug", json={"query": "테스트"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] is not None
