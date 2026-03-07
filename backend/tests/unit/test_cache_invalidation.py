"""Step 4 RED: 캐시 무효화 테스트."""
from __future__ import annotations

import io
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.api.search import set_cache_service
from app.dependencies import get_current_user, require_admin
from app.models.database import Document, DocumentStatus, get_db
from app.services.cache import CacheService


@pytest.fixture
def mock_cache():
    m = AsyncMock(spec=CacheService)
    m.invalidate_search = AsyncMock()
    m.invalidate_stats = AsyncMock()
    m.invalidate_settings = AsyncMock()
    m.get = AsyncMock(return_value=None)
    m.set = AsyncMock()
    return m


@pytest.fixture
def mock_db_session():
    """Mock DB session that returns a document."""
    db = AsyncMock()
    doc = MagicMock(spec=Document)
    doc.id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    doc.filename = "test.pdf"
    doc.file_path = "/tmp/test.pdf"
    doc.file_type = "pdf"
    doc.file_size = 1000
    doc.status = DocumentStatus.INDEXED
    doc.chunk_count = 10
    doc.source = "uploaded"
    doc.created_at = None
    doc.updated_at = None
    db.get = AsyncMock(return_value=doc)
    db.delete = AsyncMock()
    db.commit = AsyncMock()
    db.add = MagicMock()
    db.refresh = AsyncMock()
    return db


@pytest_asyncio.fixture
async def client(mock_db_session, mock_cache):
    async def override_get_db():
        yield mock_db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: type('User', (), {'id': 1, 'email': 'a@t.com', 'name': 'admin', 'role': 'admin', 'is_active': True})()
    app.dependency_overrides[require_admin] = lambda: type('User', (), {'id': 1, 'email': 'a@t.com', 'name': 'admin', 'role': 'admin', 'is_active': True})()

    set_cache_service(mock_cache)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
    set_cache_service(None)


class TestDocumentCacheInvalidation:

    @pytest.mark.asyncio
    async def test_delete_invalidates_search_cache(self, client, mock_cache):
        """문서 삭제 시 검색 캐시 삭제."""
        doc_id = "00000000-0000-0000-0000-000000000001"

        with patch("os.path.exists", return_value=False):
            resp = await client.delete(f"/api/documents/{doc_id}")

        assert resp.status_code == 200
        mock_cache.invalidate_search.assert_awaited()
        mock_cache.invalidate_stats.assert_awaited()

    @pytest.mark.asyncio
    @patch("app.api.documents.index_document_task", create=True)
    async def test_reindex_invalidates_search_cache(self, mock_task, client, mock_cache):
        """재인덱싱 시 검색 캐시 삭제."""
        doc_id = "00000000-0000-0000-0000-000000000001"

        with patch("app.api.documents.index_document_task") as mock_idx:
            mock_idx.delay = MagicMock()
            resp = await client.post(f"/api/documents/{doc_id}/reindex")

        assert resp.status_code == 200
        mock_cache.invalidate_search.assert_awaited()
        mock_cache.invalidate_stats.assert_awaited()
