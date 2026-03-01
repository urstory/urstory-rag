"""Step 2.5 RED: 커스텀 예외 및 전역 핸들러 테스트."""
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_rag_exception_handler():
    """RAGException 발생 시 JSON 응답 형식 검증."""
    from app.exceptions import RAGException

    @app.get("/api/_test_exception")
    async def _raise():
        raise RAGException("test error")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/_test_exception")

    assert response.status_code == 500
    data = response.json()
    assert data["error"] == "INTERNAL_ERROR"
    assert data["message"] == "test error"


@pytest.mark.asyncio
async def test_document_not_found():
    """404 + DOCUMENT_NOT_FOUND 확인."""
    from app.exceptions import DocumentNotFoundError

    @app.get("/api/_test_not_found")
    async def _raise():
        raise DocumentNotFoundError("document abc not found")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/_test_not_found")

    assert response.status_code == 404
    data = response.json()
    assert data["error"] == "DOCUMENT_NOT_FOUND"
    assert "abc" in data["message"]


@pytest.mark.asyncio
async def test_guardrail_violation():
    """400 + GUARDRAIL_VIOLATION 확인."""
    from app.exceptions import GuardrailViolation

    @app.get("/api/_test_guardrail")
    async def _raise():
        raise GuardrailViolation("PII detected")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/_test_guardrail")

    assert response.status_code == 400
    data = response.json()
    assert data["error"] == "GUARDRAIL_VIOLATION"


@pytest.mark.asyncio
async def test_embedding_service_error():
    """503 + EMBEDDING_SERVICE_ERROR 확인."""
    from app.exceptions import EmbeddingServiceError

    @app.get("/api/_test_embedding_error")
    async def _raise():
        raise EmbeddingServiceError("Ollama unreachable")

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/_test_embedding_error")

    assert response.status_code == 503
    data = response.json()
    assert data["error"] == "EMBEDDING_SERVICE_ERROR"
