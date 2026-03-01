"""Step 3.3: 듀얼 인덱서 단위 테스트 (RED → GREEN)."""
from unittest.mock import AsyncMock

import pytest

from app.services.chunking.base import Chunk
from app.services.document.indexer import DocumentIndexer


@pytest.fixture
def mock_deps():
    embedding = AsyncMock()
    embedding.embed_documents.return_value = [
        [0.1] * 1024,
        [0.2] * 1024,
    ]
    pg_store = AsyncMock()
    es_store = AsyncMock()
    return embedding, pg_store, es_store


@pytest.fixture
def sample_chunks():
    return [
        Chunk(content="첫 번째 청크입니다.", chunk_index=0, metadata={}),
        Chunk(content="두 번째 청크입니다.", chunk_index=1, metadata={}),
    ]


class TestDocumentIndexer:
    @pytest.mark.asyncio
    async def test_index_document(self, mock_deps, sample_chunks):
        """인덱싱 후 PGVector와 ES 양쪽에 저장 확인."""
        embedding, pg_store, es_store = mock_deps
        indexer = DocumentIndexer(embedding, pg_store, es_store)

        await indexer.index("doc-123", sample_chunks)

        embedding.embed_documents.assert_called_once_with(
            ["첫 번째 청크입니다.", "두 번째 청크입니다."]
        )
        pg_store.write.assert_called_once()
        es_store.write.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_document(self, mock_deps, sample_chunks):
        """삭제 후 양쪽에서 제거 확인."""
        embedding, pg_store, es_store = mock_deps
        indexer = DocumentIndexer(embedding, pg_store, es_store)

        await indexer.delete("doc-123")

        pg_store.delete.assert_called_once_with(filters={"doc_id": "doc-123"})
        es_store.delete.assert_called_once_with(filters={"doc_id": "doc-123"})

    @pytest.mark.asyncio
    async def test_index_with_embeddings(self, mock_deps, sample_chunks):
        """임베딩 차원(1024) 확인."""
        embedding, pg_store, es_store = mock_deps
        indexer = DocumentIndexer(embedding, pg_store, es_store)

        await indexer.index("doc-123", sample_chunks)

        # pg_store.write 호출 시 전달된 embeddings 확인
        call_args = pg_store.write.call_args
        embeddings = call_args[0][1]  # 두 번째 위치 인자
        assert len(embeddings) == 2
        assert len(embeddings[0]) == 1024

    @pytest.mark.asyncio
    async def test_index_empty_chunks(self, mock_deps):
        """빈 청크 리스트 인덱싱 시 아무 작업 안 함."""
        embedding, pg_store, es_store = mock_deps
        indexer = DocumentIndexer(embedding, pg_store, es_store)

        await indexer.index("doc-123", [])

        embedding.embed_documents.assert_not_called()
        pg_store.write.assert_not_called()
        es_store.write.assert_not_called()
