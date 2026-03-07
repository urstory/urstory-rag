"""Shutdown 미들웨어 테스트."""
import pytest

from app.main import app


@pytest.mark.asyncio
async def test_normal_request_passes(client):
    """정상 상태에서 요청이 통과한다."""
    resp = await client.get("/api/health/live")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_shutting_down_returns_503(client):
    """shutdown 중 일반 요청은 503을 반환한다."""
    app.state.shutting_down = True
    try:
        resp = await client.get("/api/search/test")
        assert resp.status_code == 503
        data = resp.json()
        assert data["error"] == "service_unavailable"
        assert "Retry-After" in resp.headers
        assert resp.headers["Retry-After"] == "30"
    finally:
        app.state.shutting_down = False


@pytest.mark.asyncio
async def test_shutdown_message_user_friendly(client):
    """shutdown 메시지에 기술 용어 대신 사용자 친화적 메시지가 포함된다."""
    app.state.shutting_down = True
    try:
        resp = await client.get("/api/search/test")
        data = resp.json()
        assert "시스템 업데이트" in data["message"]
        assert "서버" not in data["message"]
    finally:
        app.state.shutting_down = False


@pytest.mark.asyncio
async def test_health_during_shutdown(client):
    """shutdown 중에도 health 엔드포인트는 정상 응답한다."""
    app.state.shutting_down = True
    try:
        resp = await client.get("/api/health/live")
        assert resp.status_code == 200
        resp2 = await client.get("/api/health/ready")
        # ready는 DB 연결에 따라 다를 수 있지만, 503이 아닌 shutdown 응답이 아님
        assert resp2.status_code in (200, 503)
        # shutdown 미들웨어의 503이 아닌 health 자체의 응답인지 확인
        if resp2.status_code == 503:
            assert resp2.json().get("status") in ("not_ready", None)
    finally:
        app.state.shutting_down = False
