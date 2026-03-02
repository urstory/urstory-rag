from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import documents, evaluation, health, monitoring, search, settings, system, watcher
from app.config import get_settings
from app.exceptions import RAGException
from app.models.database import init_db
from app.monitoring.langfuse import LangfuseMonitor


@asynccontextmanager
async def lifespan(app: FastAPI):
    env = get_settings()
    init_db(env.database_url)

    # Langfuse 모니터 초기화
    app.state.langfuse_monitor = LangfuseMonitor(
        public_key=env.langfuse_public_key,
        secret_key=env.langfuse_secret_key,
        host=env.langfuse_host,
    )

    # 검색 오케스트레이터 초기화
    from app.api import search as search_api
    from app.models.database import _async_session_factory
    from app.services.hyde.generator import HyDEGenerator
    from app.services.reranking.korean import KoreanCrossEncoder
    from app.services.search.hybrid import HybridSearchOrchestrator
    from app.services.search.keyword_es import ElasticsearchNoriEngine
    from app.services.search.vector import VectorSearchEngine
    from app.services.settings import SettingsService

    # 임베딩: OpenAI text-embedding-3-small (1536차원)
    from app.services.embedding.openai import OpenAIEmbedding
    embedder = OpenAIEmbedding(api_key=env.openai_api_key)

    # LLM: OpenAI가 있으면 gpt-4.1-mini, 없으면 Ollama
    if env.openai_api_key:
        from app.services.generation.openai import OpenAILLM
        llm = OpenAILLM(api_key=env.openai_api_key, model="gpt-4.1-mini")
    else:
        from app.services.generation.ollama import OllamaLLM
        llm = OllamaLLM(url=env.ollama_url)

    vector_engine = VectorSearchEngine(session_factory=_async_session_factory)
    keyword_engine = ElasticsearchNoriEngine(es_url=env.elasticsearch_url)
    reranker = KoreanCrossEncoder()
    hyde_generator = HyDEGenerator(llm=llm)

    orchestrator = HybridSearchOrchestrator(
        embedder=embedder,
        vector_engine=vector_engine,
        keyword_engine=keyword_engine,
        reranker=reranker,
        hyde_generator=hyde_generator,
        llm=llm,
        langfuse_monitor=app.state.langfuse_monitor,
    )
    search_api.set_orchestrator(orchestrator)

    settings_session = _async_session_factory()
    settings_service = SettingsService(db=settings_session)
    search_api.set_search_settings_service(settings_service)

    yield

    # 종료 시 정리
    await settings_session.close()
    app.state.langfuse_monitor.flush()


app = FastAPI(title="UrstoryRAG", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RAGException)
async def rag_exception_handler(request: Request, exc: RAGException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.error_code, "message": str(exc)},
    )


app.include_router(health.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(watcher.router, prefix="/api")
app.include_router(system.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(evaluation.router, prefix="/api")
app.include_router(monitoring.router, prefix="/api")
