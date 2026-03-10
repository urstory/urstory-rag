"""문서 인덱싱 비동기 태스크 (강화된 재시도 로직)."""
import asyncio
import logging

from app.worker import celery_app

logger = logging.getLogger(__name__)


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
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # RAG 설정 로드 (embedding_model, contextual chunking 등)
    from app.services.settings import SettingsService
    settings_service = SettingsService()
    rag_settings_session = session_factory()
    settings_service._db = rag_settings_session
    rag_settings = await settings_service.get_settings()
    await rag_settings_session.close()

    # 임베딩: OpenAI (설정에서 모델명 로드)
    from app.services.embedding.openai import OpenAIEmbedding
    embedding = OpenAIEmbedding(api_key=settings.openai_api_key, model=rag_settings.embedding_model, dimensions=1536)
    converter = DocumentConverter(
        pdf_parser=rag_settings.pdf_parser,
        ocr_enabled=rag_settings.ocr_enabled,
        ocr_languages=rag_settings.ocr_languages,
        table_extraction_enabled=rag_settings.table_extraction_enabled,
    )

    from app.services.document.stores.pgvector_store import PgVectorStore
    from app.services.document.stores.elasticsearch_store import ElasticsearchStore

    pg_store = PgVectorStore(session_factory=session_factory)
    es_store = ElasticsearchStore(es_url=settings.elasticsearch_url)
    indexer = DocumentIndexer(embedding, pg_store, es_store)

    # Contextual Chunking LLM 프로바이더 (조건부 생성)
    chunk_llm = None
    if rag_settings.contextual_chunking_enabled:
        from app.services.generation.openai import OpenAILLM
        chunk_llm = OpenAILLM(
            api_key=settings.openai_api_key,
            model=rag_settings.contextual_chunking_model,
        )

    session = session_factory()
    processor = DocumentProcessor(
        converter=converter,
        indexer=indexer,
        db_session=session,
        chunking_strategy=rag_settings.chunking_strategy,
        embedder=embedding,
        llm_provider=chunk_llm,
        contextual_chunking_enabled=rag_settings.contextual_chunking_enabled,
        contextual_chunking_max_doc_chars=rag_settings.contextual_chunking_max_doc_chars,
    )
    return processor


async def _run_indexing(doc_id: str):
    """단일 이벤트 루프에서 문서 인덱싱 전체 파이프라인을 실행."""
    file_path = await get_document_file_path(doc_id)
    processor = await create_processor()
    await processor.process(doc_id, file_path)


@celery_app.task(
    bind=True,
    max_retries=5,
    autoretry_for=(Exception,),
    retry_backoff=60,
    retry_backoff_max=600,
    retry_jitter=True,
)
def index_document_task(self, doc_id: str):
    """문서 인덱싱 비동기 태스크.

    재시도 전략:
    - 최대 5회 재시도 (기존 3회에서 강화)
    - Exponential Backoff: 60초 → 120초 → 240초 → 480초 → 600초(max)
    - jitter 추가 (thundering herd 방지)
    """
    try:
        asyncio.run(_run_indexing(doc_id))
    except Exception as exc:
        logger.error(
            "문서 인덱싱 실패 (재시도 %d/%d) — doc_id=%s, error=%s",
            self.request.retries, self.max_retries, doc_id, str(exc)[:200],
        )
        raise
