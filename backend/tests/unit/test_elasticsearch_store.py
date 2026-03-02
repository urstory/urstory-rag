"""ElasticsearchStore 단위 테스트."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.chunking.base import Chunk
from app.services.document.stores.elasticsearch_store import ElasticsearchStore


class TestElasticsearchStore:
    @pytest.mark.asyncio
    async def test_write_bulk_indexes(self):
        store = ElasticsearchStore(es_url="http://test:9200")
        chunks = [Chunk(content="테스트 청크", chunk_index=0, metadata={"page": 1})]

        mock_head = MagicMock(status_code=200)
        mock_bulk = MagicMock(status_code=200)
        mock_bulk.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.head", new_callable=AsyncMock, return_value=mock_head):
            with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_bulk) as mock_post:
                await store.write(chunks, meta={"doc_id": "doc-123"})

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert "테스트 청크" in call_kwargs.kwargs.get("content", "")

    @pytest.mark.asyncio
    async def test_write_creates_index_if_missing(self):
        store = ElasticsearchStore(es_url="http://test:9200")
        chunks = [Chunk(content="test", chunk_index=0)]

        mock_head_404 = MagicMock(status_code=404)
        mock_put = MagicMock(status_code=200)
        mock_put.raise_for_status = MagicMock()
        mock_bulk = MagicMock(status_code=200)
        mock_bulk.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.head", new_callable=AsyncMock, return_value=mock_head_404):
            with patch("httpx.AsyncClient.put", new_callable=AsyncMock, return_value=mock_put) as mock_put_call:
                with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_bulk):
                    await store.write(chunks, meta={"doc_id": "doc-123"})

        mock_put_call.assert_called_once()
        body = mock_put_call.call_args.kwargs.get("json", {})
        assert "nori_analyzer" in str(body)

    @pytest.mark.asyncio
    async def test_delete_by_doc_id(self):
        store = ElasticsearchStore(es_url="http://test:9200")

        mock_resp = MagicMock(status_code=200)
        mock_resp.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp) as mock_post:
            await store.delete(filters={"doc_id": "doc-123"})

        body = mock_post.call_args.kwargs.get("json", {})
        assert body["query"]["term"]["document_id"] == "doc-123"

    @pytest.mark.asyncio
    async def test_delete_ignores_404(self):
        store = ElasticsearchStore(es_url="http://test:9200")

        mock_resp = MagicMock(status_code=404)

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_resp):
            await store.delete(filters={"doc_id": "doc-123"})
