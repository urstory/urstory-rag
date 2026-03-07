"""Step 5 RED: 캐시 메트릭 관리자 API 테스트."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.api.search import set_cache_service
from app.dependencies import get_current_user, require_admin
from app.models.database import get_db
from app.services.cache import CacheService


@pytest.fixture
def mock_cache():
    m = AsyncMock(spec=CacheService)
    m.enabled = True
    m.get_metrics.return_value = {
        "hits": 80,
        "misses": 20,
        "hit_rate": 0.8,
        "total_requests": 100,
    }
    m.get_redis_info = AsyncMock(return_value={
        "cache_key_count": 42,
        "used_memory_human": "2.5M",
        "used_memory_bytes": 2621440,
    })
    m.invalidate_all = AsyncMock(return_value=42)
    m.get = AsyncMock(return_value=None)
    m.set = AsyncMock()
    return m


def _fake_admin():
    return type('User', (), {'id': 1, 'email': 'a@t.com', 'name': 'admin', 'role': 'admin', 'is_active': True})()


def _fake_user():
    return type('User', (), {'id': 2, 'email': 'u@t.com', 'name': 'user', 'role': 'user', 'is_active': True})()


@pytest_asyncio.fixture
async def admin_client(mock_cache):
    """관리자 권한 클라이언트."""
    mock_db = AsyncMock()

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = _fake_admin
    app.dependency_overrides[require_admin] = _fake_admin

    set_cache_service(mock_cache)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
    set_cache_service(None)


class TestCacheMetricsAPI:

    @pytest.mark.asyncio
    async def test_get_cache_metrics(self, admin_client, mock_cache):
        """메트릭 응답 형식 확인."""
        resp = await admin_client.get("/api/monitoring/cache")

        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is True
        assert data["hits"] == 80
        assert data["misses"] == 20
        assert data["hit_rate"] == 0.8
        assert data["cache_key_count"] == 42
        assert data["used_memory_human"] == "2.5M"

    @pytest.mark.asyncio
    async def test_clear_cache(self, admin_client, mock_cache):
        """수동 비우기 후 삭제 수 반환."""
        resp = await admin_client.delete("/api/monitoring/cache")

        assert resp.status_code == 200
        data = resp.json()
        assert data["cleared"] == 42
        mock_cache.invalidate_all.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_cache_metrics_no_cache_service(self):
        """CacheService가 없을 때 기본값 반환."""
        mock_db = AsyncMock()

        async def override_get_db():
            yield mock_db

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_user] = _fake_admin
        app.dependency_overrides[require_admin] = _fake_admin
        set_cache_service(None)

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.get("/api/monitoring/cache")

        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is False
        assert data["hits"] == 0

        app.dependency_overrides.clear()
