"""Step 2.7 RED: 헬스체크 API 확장 테스트."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_health_all_connected():
    """모든 컴포넌트 connected 확인."""
    with (
        patch("app.api.health.check_db", new_callable=AsyncMock, return_value=True),
        patch("app.api.health.check_elasticsearch", new_callable=AsyncMock, return_value=True),
        patch("app.api.health.check_ollama", new_callable=AsyncMock, return_value=True),
        patch("app.api.health.check_redis", new_callable=AsyncMock, return_value=True),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["components"]["database"] == "connected"
    assert data["components"]["elasticsearch"] == "connected"
    assert data["components"]["ollama"] == "connected"
    assert data["components"]["redis"] == "connected"


@pytest.mark.asyncio
async def test_health_db_disconnected():
    """DB 실패 시 disconnected 표시 확인."""
    with (
        patch("app.api.health.check_db", new_callable=AsyncMock, return_value=False),
        patch("app.api.health.check_elasticsearch", new_callable=AsyncMock, return_value=True),
        patch("app.api.health.check_ollama", new_callable=AsyncMock, return_value=True),
        patch("app.api.health.check_redis", new_callable=AsyncMock, return_value=True),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["components"]["database"] == "disconnected"
    assert data["components"]["elasticsearch"] == "connected"


@pytest.mark.asyncio
async def test_health_multiple_disconnected():
    """여러 컴포넌트 실패 시에도 200 응답."""
    with (
        patch("app.api.health.check_db", new_callable=AsyncMock, return_value=False),
        patch("app.api.health.check_elasticsearch", new_callable=AsyncMock, return_value=False),
        patch("app.api.health.check_ollama", new_callable=AsyncMock, return_value=True),
        patch("app.api.health.check_redis", new_callable=AsyncMock, return_value=False),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/health")

    assert response.status_code == 200
    data = response.json()
    assert data["components"]["database"] == "disconnected"
    assert data["components"]["elasticsearch"] == "disconnected"
    assert data["components"]["ollama"] == "connected"
    assert data["components"]["redis"] == "disconnected"
