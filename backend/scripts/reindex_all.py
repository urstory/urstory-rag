"""순차 재인덱싱 스크립트 — Celery 우회, 한 문서씩 처리."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

async def main():
    from sqlalchemy import select, text
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.config import get_settings
    from app.models.database import Document
    from app.services.document.converter import DocumentConverter
    from app.services.document.indexer import DocumentIndexer
    from app.services.document.processor import DocumentProcessor
    from app.services.document.stores.pgvector_store import PgVectorStore
    from app.services.document.stores.elasticsearch_store import ElasticsearchStore
    from app.services.embedding.openai import OpenAIEmbedding
    from app.services.settings import SettingsService

    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # 문서 목록 조회
    async with session_factory() as session:
        result = await session.execute(select(Document.id, Document.file_path, Document.filename))
        docs = [(str(r[0]), r[1], r[2]) for r in result.all()]

    print(f"총 {len(docs)}개 문서 재인덱싱 시작")

    # ES 현재 상태
    import httpx
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{settings.elasticsearch_url}/rag_chunks/_count")
            print(f"ES 청크 수 (재인덱싱 전): {resp.json().get('count', 0)}")
        except Exception:
            print("ES 인덱스 없음 (새로 생성됩니다)")

    # RAG 설정 로드
    async with session_factory() as session:
        settings_service = SettingsService()
        settings_service._db = session
        rag_settings = await settings_service.get_settings()

    embedding = OpenAIEmbedding(api_key=settings.openai_api_key, model=rag_settings.embedding_model, dimensions=1536)
    converter = DocumentConverter()

    # Contextual Chunking LLM 프로바이더 (조건부 생성)
    chunk_llm = None
    if rag_settings.contextual_chunking_enabled:
        from app.services.generation.openai import OpenAILLM
        chunk_llm = OpenAILLM(
            api_key=settings.openai_api_key,
            model=rag_settings.contextual_chunking_model,
        )
        print(f"Contextual Chunking: ON (model={rag_settings.contextual_chunking_model})")
    else:
        print("Contextual Chunking: OFF")

    for i, (doc_id, file_path, filename) in enumerate(docs, 1):
        print(f"\n[{i}/{len(docs)}] {filename} (ID: {doc_id[:8]}...)")

        pg_store = PgVectorStore(session_factory=session_factory)
        es_store = ElasticsearchStore(es_url=settings.elasticsearch_url)
        indexer = DocumentIndexer(embedding, pg_store, es_store)

        async with session_factory() as session:
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
            try:
                await processor.process(doc_id, file_path)
                print(f"  OK")
            except Exception as e:
                print(f"  ERROR: {e}")

    # ES 최종 상태
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{settings.elasticsearch_url}/rag_chunks/_count")
            print(f"\nES 청크 수 (재인덱싱 후): {resp.json().get('count', 0)}")
        except Exception:
            print("\nES 청크 수 확인 실패")

    await engine.dispose()
    print("완료!")

if __name__ == "__main__":
    asyncio.run(main())
