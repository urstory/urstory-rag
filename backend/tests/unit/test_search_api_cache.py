"""Step 3 RED: 검색 API 캐싱 단위 테스트."""
from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.config import RAGSettings
from app.main import app
from app.api.search import get_orchestrator, get_search_settings_service, set_cache_service, get_cache_service
from app.dependencies import get_current_user, require_admin
from app.models.schemas import PipelineStep, SearchPipelineResult, SearchResult
from app.services.cache import CacheService

DOC_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a1")
CHUNK_A = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _make_pipeline_result() -> SearchPipelineResult:
    docs = [
        SearchResult(chunk_id=CHUNK_A, document_id=DOC_ID, content="연차 신청은...", score=0.95),
    ]
    return SearchPipelineResult(
        documents=docs,
        answer="연차 신청은 인사시스템에서 진행합니다.",
        trace=[],
    )


@pytest.fixture
def mock_orchestrator():
    m = AsyncMock()
    m.search.return_value = _make_pipeline_result()
    return m


@pytest.fixture
def mock_settings_service():
    m = AsyncMock()
    m.get_settings.return_value = RAGSettings()
    return m


@pytest.fixture
def mock_cache_service():
    """실제 Redis 대신 모든 메서드를 mock한 CacheService."""
    m = AsyncMock(spec=CacheService)
    m.enabled = True
    m.get_search = AsyncMock(return_value=None)
    m.set_search = AsyncMock()
    m.compute_settings_hash = CacheService.compute_settings_hash  # 정적 메서드는 실제 사용
    return m


@pytest_asyncio.fixture
async def client(mock_orchestrator, mock_settings_service, mock_cache_service):
    app.dependency_overrides[get_orchestrator] = lambda: mock_orchestrator
    app.dependency_overrides[get_search_settings_service] = lambda: mock_settings_service
    app.dependency_overrides[get_current_user] = lambda: type('User', (), {'id': 1, 'email': 'a@t.com', 'name': 'admin', 'role': 'admin', 'is_active': True})()
    app.dependency_overrides[require_admin] = lambda: type('User', (), {'id': 1, 'email': 'a@t.com', 'name': 'admin', 'role': 'admin', 'is_active': True})()

    # 캐시 서비스 주입
    set_cache_service(mock_cache_service)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
    set_cache_service(None)


class TestSearchCacheIntegration:
    """검색 API + 캐시 통합 테스트."""

    @pytest.mark.asyncio
    async def test_search_cache_miss_calls_orchestrator(self, client, mock_orchestrator, mock_cache_service):
        """캐시 미스 시 orchestrator.search() 호출됨."""
        mock_cache_service.get_search.return_value = None

        resp = await client.post("/api/search", json={"query": "연차 신청 방법"})

        assert resp.status_code == 200
        mock_orchestrator.search.assert_called_once()
        mock_cache_service.set_search.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_cache_hit_skips_orchestrator(self, client, mock_orchestrator, mock_cache_service):
        """캐시 히트 시 orchestrator.search() 미호출."""
        cached_data = {
            "query": "연차 신청 방법",
            "answer": "캐시된 답변",
            "results": [
                {
                    "chunk_id": str(CHUNK_A),
                    "document_id": str(DOC_ID),
                    "content": "캐시 결과",
                    "score": 0.9,
                }
            ],
        }
        mock_cache_service.get_search.return_value = cached_data

        resp = await client.post("/api/search", json={"query": "연차 신청 방법"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["answer"] == "캐시된 답변"
        mock_orchestrator.search.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_cache_stores_result(self, client, mock_cache_service):
        """첫 검색 후 캐시에 저장됨."""
        mock_cache_service.get_search.return_value = None

        await client.post("/api/search", json={"query": "테스트"})

        mock_cache_service.set_search.assert_called_once()
        call_args = mock_cache_service.set_search.call_args
        assert call_args[0][0] == "테스트"  # query

    @pytest.mark.asyncio
    async def test_search_cache_disabled(self, client, mock_orchestrator, mock_settings_service, mock_cache_service):
        """cache_enabled=False 시 캐시 미사용."""
        disabled_settings = RAGSettings(cache_enabled=False)
        mock_settings_service.get_settings.return_value = disabled_settings

        resp = await client.post("/api/search", json={"query": "테스트"})

        assert resp.status_code == 200
        mock_orchestrator.search.assert_called_once()
        mock_cache_service.get_search.assert_not_called()
        mock_cache_service.set_search.assert_not_called()

    @pytest.mark.asyncio
    async def test_search_debug_bypasses_cache(self, client, mock_orchestrator, mock_cache_service):
        """디버그 API는 캐시 무시."""
        mock_orchestrator.search.return_value = _make_pipeline_result()

        resp = await client.post("/api/search/debug", json={"query": "연차"})

        assert resp.status_code == 200
        mock_orchestrator.search.assert_called_once()
        # 디버그 API는 캐시를 조회/저장하지 않음
        mock_cache_service.get_search.assert_not_called()
        mock_cache_service.set_search.assert_not_called()


class TestCacheHeader:
    """X-Cache 헤더 테스트."""

    @pytest.mark.asyncio
    async def test_cache_header_miss(self, client, mock_cache_service):
        """캐시 미스 시 X-Cache: MISS."""
        mock_cache_service.get_search.return_value = None

        resp = await client.post("/api/search", json={"query": "테스트"})

        assert resp.headers.get("X-Cache") == "MISS"

    @pytest.mark.asyncio
    async def test_cache_header_hit(self, client, mock_cache_service):
        """캐시 히트 시 X-Cache: HIT."""
        cached_data = {
            "query": "테스트",
            "answer": "캐시 답변",
            "results": [],
        }
        mock_cache_service.get_search.return_value = cached_data

        resp = await client.post("/api/search", json={"query": "테스트"})

        assert resp.headers.get("X-Cache") == "HIT"
