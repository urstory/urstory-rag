"""Health Probe 엔드포인트 테스트."""
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_liveness_always_200(client):
    resp = await client.get("/api/health/live")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_health_includes_version(client):
    with patch("app.api.health.check_db", new_callable=AsyncMock, return_value=True), \
         patch("app.api.health.check_elasticsearch", new_callable=AsyncMock, return_value=True), \
         patch("app.api.health.check_openai", new_callable=AsyncMock, return_value=True), \
         patch("app.api.health.check_redis", new_callable=AsyncMock, return_value=True):
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "version" in data


@pytest.mark.asyncio
async def test_health_all_connected(client):
    with patch("app.api.health.check_db", new_callable=AsyncMock, return_value=True), \
         patch("app.api.health.check_elasticsearch", new_callable=AsyncMock, return_value=True), \
         patch("app.api.health.check_openai", new_callable=AsyncMock, return_value=True), \
         patch("app.api.health.check_redis", new_callable=AsyncMock, return_value=True):
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_health_degraded(client):
    with patch("app.api.health.check_db", new_callable=AsyncMock, return_value=False), \
         patch("app.api.health.check_elasticsearch", new_callable=AsyncMock, return_value=True), \
         patch("app.api.health.check_openai", new_callable=AsyncMock, return_value=True), \
         patch("app.api.health.check_redis", new_callable=AsyncMock, return_value=True):
        resp = await client.get("/api/health")
        data = resp.json()
        assert data["status"] == "degraded"


@pytest.mark.asyncio
async def test_health_openai_down_still_ok(client):
    with patch("app.api.health.check_db", new_callable=AsyncMock, return_value=True), \
         patch("app.api.health.check_elasticsearch", new_callable=AsyncMock, return_value=True), \
         patch("app.api.health.check_openai", new_callable=AsyncMock, return_value=False), \
         patch("app.api.health.check_redis", new_callable=AsyncMock, return_value=True):
        resp = await client.get("/api/health")
        data = resp.json()
        assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_health_includes_component_details(client):
    with patch("app.api.health.check_db", new_callable=AsyncMock, return_value=True), \
         patch("app.api.health.check_elasticsearch", new_callable=AsyncMock, return_value=True), \
         patch("app.api.health.check_openai", new_callable=AsyncMock, return_value=True), \
         patch("app.api.health.check_redis", new_callable=AsyncMock, return_value=True):
        resp = await client.get("/api/health")
        data = resp.json()
        db = data["components"]["database"]
        assert "description" in db
        assert "impact" in db
        assert "required" in db


@pytest.mark.asyncio
async def test_readiness_all_ok(client):
    with patch("app.api.health.check_db", new_callable=AsyncMock, return_value=True), \
         patch("app.api.health.check_elasticsearch", new_callable=AsyncMock, return_value=True), \
         patch("app.api.health.check_redis", new_callable=AsyncMock, return_value=True):
        resp = await client.get("/api/health/ready")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_readiness_db_down(client):
    with patch("app.api.health.check_db", new_callable=AsyncMock, return_value=False), \
         patch("app.api.health.check_elasticsearch", new_callable=AsyncMock, return_value=True), \
         patch("app.api.health.check_redis", new_callable=AsyncMock, return_value=True):
        resp = await client.get("/api/health/ready")
        assert resp.status_code == 503
        assert resp.json()["status"] == "not_ready"
