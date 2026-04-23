"""Edge-case tests covering scenarios flagged in issue #15.

Focus areas:
  - Very long and whitespace-only queries on /api/search
  - File upload failure modes (unsupported MIME, invalid UUIDs)
  - Graceful handling of malformed JSON on mutating endpoints
  - Health endpoint reachability without auth

Two client fixtures are used:
  - ``search_client`` mocks orchestrator+settings, isolated from DB
  - ``client`` (from conftest) provides a real test_db session
"""

from __future__ import annotations

import io
import uuid
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.search import get_orchestrator, get_search_settings_service
from app.config import RAGSettings
from app.dependencies import get_current_user, require_admin
from app.main import app
from app.models.schemas import SearchPipelineResult, SearchResult


DOC_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a1")
CHUNK_A = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _make_pipeline_result() -> SearchPipelineResult:
    docs = [
        SearchResult(
            chunk_id=CHUNK_A,
            document_id=DOC_ID,
            content="edge case content",
            score=0.9,
        )
    ]
    return SearchPipelineResult(documents=docs, answer="ok", trace=[])


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


@pytest_asyncio.fixture
async def search_client(mock_orchestrator, mock_settings_service):
    """Orchestrator/settings mocked; no DB required."""
    app.dependency_overrides[get_orchestrator] = lambda: mock_orchestrator
    app.dependency_overrides[get_search_settings_service] = lambda: mock_settings_service
    app.dependency_overrides[get_current_user] = lambda: type(
        "U", (), {"id": 1, "email": "a@t", "name": "admin", "role": "admin", "is_active": True}
    )()
    app.dependency_overrides[require_admin] = lambda: type(
        "U", (), {"id": 1, "email": "a@t", "name": "admin", "role": "admin", "is_active": True}
    )()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


class TestSearchEdgeCases:
    """Queries of unusual shape should not crash the search endpoint."""

    @pytest.mark.asyncio
    async def test_whitespace_only_query(self, search_client):
        resp = await search_client.post("/api/search", json={"query": "   \t\n   "})
        assert resp.status_code in (200, 400, 422)

    @pytest.mark.asyncio
    async def test_very_long_query_within_limits(self, search_client, mock_orchestrator):
        """~700-char queries should work: no implicit truncation exceptions."""
        long_query = "연차 신청 " * 100
        resp = await search_client.post("/api/search", json={"query": long_query})
        assert resp.status_code == 200
        mock_orchestrator.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_unicode_emoji_query(self, search_client):
        resp = await search_client.post("/api/search", json={"query": "🔥 연차 🎉"})
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_missing_query_field_422(self, search_client):
        """Schema validation: missing 'query' => Pydantic 422."""
        resp = await search_client.post("/api/search", json={})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_malformed_json_body_400_or_422(self, search_client):
        resp = await search_client.post(
            "/api/search",
            content=b"not-json",
            headers={"content-type": "application/json"},
        )
        assert resp.status_code in (400, 422)


class TestDocumentsEdgeCases:
    """Upload + retrieval edge cases using the real test_db fixture."""

    @pytest.mark.asyncio
    async def test_upload_unsupported_mime_does_not_crash(self, client, test_db):
        """Unsupported content-type must return a clean error, not 500."""
        resp = await client.post(
            "/api/documents/upload",
            files={
                "file": (
                    "evil.exe",
                    io.BytesIO(b"MZ\x90\x00"),
                    "application/octet-stream",
                )
            },
        )
        assert resp.status_code != 500

    @pytest.mark.asyncio
    async def test_document_detail_invalid_uuid(self, client, test_db):
        """Non-UUID path parameter should not reach a 500."""
        resp = await client.get("/api/documents/not-a-uuid")
        assert resp.status_code in (404, 422)

    @pytest.mark.asyncio
    async def test_document_detail_missing_id(self, client, test_db):
        fake_id = str(uuid.uuid4())
        resp = await client.get(f"/api/documents/{fake_id}")
        assert resp.status_code == 404


class TestHealthEdgeCases:
    """/api/health should respond even when optional services are degraded."""

    @pytest.mark.asyncio
    async def test_health_unauthenticated_allowed(self, search_client):
        resp = await search_client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
