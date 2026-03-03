"""문서 처리 오케스트레이터: 변환 → 청킹 → 인덱싱 전체 파이프라인."""
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Document, DocumentStatus
from app.services.chunking.auto_detect import AutoDetectChunking
from app.services.chunking.header import SectionHeaderChunking
from app.services.chunking.recursive import RecursiveChunking
from app.services.chunking.semantic import SemanticChunking
from app.services.document.converter import DocumentConverter
from app.services.document.indexer import DocumentIndexer
from app.services.embedding.base import EmbeddingProvider
from app.services.generation.base import LLMProvider


class DocumentProcessor:
    """파일 변환 → 청킹 전략 선택 → 청킹 → 듀얼 인덱싱."""

    def __init__(
        self,
        converter: DocumentConverter,
        indexer: DocumentIndexer,
        db_session: AsyncSession,
        chunking_strategy: str = "auto",
        embedder: EmbeddingProvider | None = None,
        llm_provider: LLMProvider | None = None,
        contextual_chunking_enabled: bool = False,
        contextual_chunking_max_doc_chars: int = 2000,
    ):
        self.converter = converter
        self.indexer = indexer
        self.db_session = db_session
        self.chunking_strategy = chunking_strategy
        self.embedder = embedder
        self.llm_provider = llm_provider
        self.contextual_chunking_enabled = contextual_chunking_enabled
        self.contextual_chunking_max_doc_chars = contextual_chunking_max_doc_chars

    async def process(self, doc_id: str, file_path: str):
        try:
            # 1. 파일 변환
            document = await self.converter.convert(file_path)

            # 2. 청킹 전략 선택
            chunker = self._get_chunking_strategy()

            # 3. 청킹
            chunks = await chunker.chunk(document.content, document.meta)

            # 4. 기존 청크 삭제 후 듀얼 인덱싱
            await self.indexer.delete(doc_id)
            await self.indexer.index(doc_id, chunks)

            # 5. DB 상태 업데이트
            await self._update_status(doc_id, DocumentStatus.INDEXED, len(chunks))

        except Exception:
            await self._update_status(doc_id, DocumentStatus.FAILED)
            raise

    def _get_chunking_strategy(self):
        strategies = {
            "recursive": lambda: RecursiveChunking(),
            "recursive_1024": lambda: RecursiveChunking(chunk_size=1024, chunk_overlap=200),
            "header": lambda: SectionHeaderChunking(chunk_size=1024, chunk_overlap=200),
            "auto": lambda: AutoDetectChunking(
                llm_provider=self.llm_provider,
                contextual_enabled=self.contextual_chunking_enabled,
                max_doc_chars=self.contextual_chunking_max_doc_chars,
            ),
            "semantic": lambda: SemanticChunking(
                embedding_provider=self.embedder, threshold=0.5
            ) if self.embedder else AutoDetectChunking(),
        }
        factory = strategies.get(self.chunking_strategy, strategies["auto"])
        base_strategy = factory()

        # contextual chunking은 모든 전략에 데코레이터로 적용
        if (
            self.contextual_chunking_enabled
            and self.llm_provider
            and not isinstance(base_strategy, AutoDetectChunking)
        ):
            from app.services.chunking.contextual import ContextualChunking
            return ContextualChunking(
                self.llm_provider,
                base_strategy,
                max_doc_chars=self.contextual_chunking_max_doc_chars,
            )

        return base_strategy

    async def _update_status(
        self, doc_id: str, status: DocumentStatus, chunk_count: int | None = None
    ):
        stmt = update(Document).where(Document.id == doc_id).values(status=status.value)
        if chunk_count is not None:
            stmt = stmt.values(chunk_count=chunk_count)
        await self.db_session.execute(stmt)
        await self.db_session.commit()
