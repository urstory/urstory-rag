"""무중단 전체 재인덱싱 서비스."""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models.database import Document


class ReindexService:
    """모든 문서를 Celery 태스크로 재인덱싱."""

    async def start_reindex(self) -> str:
        """DB에서 모든 문서를 조회하고 각각 index_document_task를 디스패치."""
        from app.tasks.indexing import index_document_task

        settings = get_settings()
        engine = create_async_engine(settings.database_url, echo=False)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        task_id = str(uuid.uuid4())

        async with session_factory() as session:
            result = await session.execute(select(Document.id))
            doc_ids = [str(row[0]) for row in result.all()]

        await engine.dispose()

        for doc_id in doc_ids:
            index_document_task.delay(doc_id)

        return task_id
