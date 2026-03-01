"""문서 인덱싱 비동기 태스크."""
import asyncio

from app.worker import celery_app


async def get_document_file_path(doc_id: str) -> str:
    """documents 테이블에서 doc_id로 파일 저장 경로를 조회."""
    from app.config import get_settings
    from app.models.database import Document, init_db, _async_session_factory
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        doc = await session.get(Document, doc_id)
        if not doc:
            raise ValueError(f"Document {doc_id} not found")
        file_path = doc.file_path

    await engine.dispose()
    return file_path


async def create_processor():
    """DocumentProcessor 인스턴스를 생성."""
    from app.config import get_settings
    from app.models.database import init_db, _async_session_factory
    from app.services.document.converter import DocumentConverter
    from app.services.document.indexer import DocumentIndexer
    from app.services.document.processor import DocumentProcessor
    from app.services.embedding.ollama import OllamaEmbedding
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    embedding = OllamaEmbedding(url=settings.ollama_url)
    converter = DocumentConverter()
    # pg_store, es_store는 통합 테스트 시 실제 구현으로 교체
    pg_store = None
    es_store = None
    indexer = DocumentIndexer(embedding, pg_store, es_store)

    session = session_factory()
    processor = DocumentProcessor(
        converter=converter,
        indexer=indexer,
        db_session=session,
    )
    return processor


@celery_app.task(bind=True, max_retries=3)
def index_document_task(self, doc_id: str):
    """문서 인덱싱 비동기 태스크."""
    try:
        file_path = asyncio.run(get_document_file_path(doc_id))
        processor = asyncio.run(create_processor())
        asyncio.run(processor.process(doc_id, file_path))
    except Exception as exc:
        self.retry(exc=exc, countdown=60)
