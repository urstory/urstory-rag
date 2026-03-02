"""PGVector 스토어: 청크 + 임베딩을 PostgreSQL에 저장."""
import json
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.chunking.base import Chunk


class PgVectorStore:
    """PGVector 기반 청크 저장소."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def write(
        self,
        chunks: list[Chunk],
        embeddings: list[list[float]],
        meta: dict,
    ) -> None:
        """청크와 임베딩을 chunks 테이블에 저장."""
        doc_id = meta["doc_id"]

        async with self.session_factory() as session:
            for chunk, embedding in zip(chunks, embeddings):
                embedding_str = f"[{','.join(str(v) for v in embedding)}]"
                await session.execute(
                    text(
                        "INSERT INTO chunks "
                        "(id, document_id, content, chunk_index, metadata, embedding) "
                        "VALUES (:id, :doc_id, :content, :idx, "
                        "CAST(:meta AS jsonb), CAST(:emb AS vector))"
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "doc_id": doc_id,
                        "content": chunk.content,
                        "idx": chunk.chunk_index,
                        "meta": json.dumps(chunk.metadata or {}, ensure_ascii=False),
                        "emb": embedding_str,
                    },
                )
            await session.commit()

    async def delete(self, filters: dict) -> None:
        """특정 문서의 청크를 모두 삭제."""
        doc_id = filters["doc_id"]
        async with self.session_factory() as session:
            await session.execute(
                text("DELETE FROM chunks WHERE document_id = :doc_id"),
                {"doc_id": doc_id},
            )
            await session.commit()
