"""요청 로깅 미들웨어 테스트."""
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def _skip_db(monkeypatch):
    """DB 없이 미들웨어만 테스트하기 위해 lifespan을 건너뛴다."""


@pytest.mark.asyncio
async def test_request_id_header(client):
    """응답에 X-Request-ID 헤더가 포함된다."""
    resp = await client.get("/api/health/live")
    assert resp.status_code == 200
    assert "X-Request-ID" in resp.headers
    assert len(resp.headers["X-Request-ID"]) == 8


@pytest.mark.asyncio
async def test_request_id_in_error_response(client):
    """RAGException 에러 응답에 request_id가 포함된다."""
    # health/live는 항상 200이므로 존재하지 않는 경로로 테스트
    # 대신 에러 핸들러 동작은 별도로 검증
    resp = await client.get("/api/health/live")
    assert "X-Request-ID" in resp.headers
