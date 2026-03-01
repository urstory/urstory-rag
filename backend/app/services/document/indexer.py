"""듀얼 인덱서: PGVector + Elasticsearch 동시 저장."""
from app.services.chunking.base import Chunk
from app.services.embedding.base import EmbeddingProvider


class DocumentIndexer:
    """임베딩 생성 후 PGVector와 Elasticsearch에 동시 인덱싱."""

    def __init__(self, embedding_provider: EmbeddingProvider, pg_store, es_store):
        self.embedding_provider = embedding_provider
        self.pg_store = pg_store
        self.es_store = es_store

    async def index(self, doc_id: str, chunks: list[Chunk]):
        if not chunks:
            return

        # 1. 임베딩 생성 (배치)
        texts = [c.content for c in chunks]
        embeddings = await self.embedding_provider.embed_documents(texts)

        # 2. PGVector 저장
        await self.pg_store.write(chunks, embeddings, meta={"doc_id": doc_id})

        # 3. Elasticsearch 인덱싱
        await self.es_store.write(chunks, meta={"doc_id": doc_id})

    async def delete(self, doc_id: str):
        await self.pg_store.delete(filters={"doc_id": doc_id})
        await self.es_store.delete(filters={"doc_id": doc_id})
