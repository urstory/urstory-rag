"""PgVectorStore 단위 테스트."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.chunking.base import Chunk
from app.services.document.stores.pgvector_store import PgVectorStore


@pytest.fixture
def mock_session_factory():
    session = AsyncMock()
    ctx = AsyncMock()
    ctx.__aenter__.return_value = session
    ctx.__aexit__.return_value = None
    factory = MagicMock(return_value=ctx)
    return factory, session


class TestPgVectorStore:
    @pytest.mark.asyncio
    async def test_write_inserts_chunks(self, mock_session_factory):
        factory, session = mock_session_factory
        store = PgVectorStore(session_factory=factory)

        chunks = [
            Chunk(content="첫 번째 청크", chunk_index=0, metadata={"page": 1}),
            Chunk(content="두 번째 청크", chunk_index=1),
        ]
        embeddings = [[0.1] * 1536, [0.2] * 1536]

        await store.write(chunks, embeddings, meta={"doc_id": "doc-123"})

        assert session.execute.call_count == 2
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_by_doc_id(self, mock_session_factory):
        factory, session = mock_session_factory
        store = PgVectorStore(session_factory=factory)

        await store.delete(filters={"doc_id": "doc-123"})

        session.execute.assert_called_once()
        session.commit.assert_called_once()
