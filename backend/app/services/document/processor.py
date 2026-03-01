"""문서 처리 오케스트레이터: 변환 → 청킹 → 인덱싱 전체 파이프라인."""
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Document, DocumentStatus
from app.services.chunking.auto_detect import AutoDetectChunking
from app.services.chunking.recursive import RecursiveChunking
from app.services.document.converter import DocumentConverter
from app.services.document.indexer import DocumentIndexer


class DocumentProcessor:
    """파일 변환 → 청킹 전략 선택 → 청킹 → 듀얼 인덱싱."""

    def __init__(
        self,
        converter: DocumentConverter,
        indexer: DocumentIndexer,
        db_session: AsyncSession,
        chunking_strategy: str = "recursive",
    ):
        self.converter = converter
        self.indexer = indexer
        self.db_session = db_session
        self.chunking_strategy = chunking_strategy

    async def process(self, doc_id: str, file_path: str):
        try:
            # 1. 파일 변환
            document = await self.converter.convert(file_path)

            # 2. 청킹 전략 선택
            chunker = self._get_chunking_strategy()

            # 3. 청킹
            chunks = await chunker.chunk(document.content, document.meta)

            # 4. 듀얼 인덱싱
            await self.indexer.index(doc_id, chunks)

            # 5. DB 상태 업데이트
            await self._update_status(doc_id, DocumentStatus.INDEXED, len(chunks))

        except Exception:
            await self._update_status(doc_id, DocumentStatus.FAILED)
            raise

    def _get_chunking_strategy(self):
        strategies = {
            "recursive": lambda: RecursiveChunking(),
            "auto": lambda: AutoDetectChunking(),
        }
        factory = strategies.get(self.chunking_strategy, strategies["recursive"])
        return factory()

    async def _update_status(
        self, doc_id: str, status: DocumentStatus, chunk_count: int | None = None
    ):
        stmt = update(Document).where(Document.id == doc_id).values(status=status.value)
        if chunk_count is not None:
            stmt = stmt.values(chunk_count=chunk_count)
        await self.db_session.execute(stmt)
        await self.db_session.commit()
