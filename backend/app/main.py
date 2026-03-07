import asyncio

import structlog
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import func, select

from app.api import documents, evaluation, health, monitoring, search, settings, system, watcher
from app.api import admin, auth
from app.config import get_settings
from app.exceptions import RAGException
from app.logging_config import setup_logging
from app.middleware.logging import RequestLoggingMiddleware
from app.middleware.rate_limit import init_limiter, limiter
from app.middleware.security import SecurityHeadersMiddleware
from app.middleware.shutdown import ShutdownMiddleware
from app.models.database import User, init_db
from app.monitoring.langfuse import LangfuseMonitor
from app.sentry_config import init_sentry
from app.services.auth import hash_password, validate_password_strength

logger = structlog.get_logger()


async def _ensure_admin_user(session):
    """users 테이블이 비어있으면 환경변수에서 관리자 자동 생성."""
    count = await session.scalar(select(func.count(User.id)))
    if count > 0:
        return

    env = get_settings()
    validate_password_strength(env.admin_password)

    admin_user = User(
        username=env.admin_username,
        hashed_password=hash_password(env.admin_password),
        name="관리자",
        role="admin",
        is_active=True,
    )
    session.add(admin_user)
    await session.commit()
    logger.info("admin_user_created", username=env.admin_username)

    if env.admin_password == "ChangeMe1234!@#$":
        logger.warning("default_admin_password", message="기본 관리자 비밀번호 사용 중. 즉시 변경하세요!")


@asynccontextmanager
async def lifespan(app: FastAPI):
    env = get_settings()

    # 로깅 초기화 (가장 먼저)
    setup_logging(
        log_level=env.log_level,
        json_format=(env.log_format == "json"),
    )

    # Sentry 초기화
    init_sentry(
        dsn=env.sentry_dsn,
        environment=env.sentry_environment,
        traces_sample_rate=env.sentry_traces_sample_rate,
    )

    init_db(env.database_url)

    # Langfuse 모니터 초기화
    app.state.langfuse_monitor = LangfuseMonitor(
        public_key=env.langfuse_public_key,
        secret_key=env.langfuse_secret_key,
        host=env.langfuse_host,
    )

    # 초기 관리자 자동 생성
    from app.models.database import _async_session_factory
    if _async_session_factory:
        try:
            async with _async_session_factory() as session:
                await _ensure_admin_user(session)
        except Exception as e:
            logger.warning("admin_creation_failed", error=str(e))

    # 검색 오케스트레이터 초기화
    from app.api import search as search_api
    from app.services.generation.evidence_extractor import EvidenceExtractor
    from app.services.guardrails.numeric_verifier import NumericVerifier
    from app.services.hyde.generator import HyDEGenerator
    from app.services.reranking.korean import KoreanCrossEncoder
    from app.services.search.hybrid import HybridSearchOrchestrator
    from app.services.search.keyword_es import ElasticsearchNoriEngine
    from app.services.search.multi_query import MultiQueryGenerator
    from app.services.search.query_expander import QueryExpander
    from app.services.search.question_classifier import QuestionClassifier
    from app.services.search.vector import VectorSearchEngine
    from app.services.settings import SettingsService

    # RAG 설정 로드 (embedding_model 등)
    from app.services.embedding.openai import OpenAIEmbedding
    async with _async_session_factory() as _s:
        _ss = SettingsService(db=_s)
        _rag = await _ss.get_settings()
    embedder = OpenAIEmbedding(api_key=env.openai_api_key, model=_rag.embedding_model, dimensions=1536)

    # LLM: OpenAI gpt-4.1-mini
    from app.services.generation.openai import OpenAILLM
    llm = OpenAILLM(api_key=env.openai_api_key, model="gpt-4.1-mini")

    vector_engine = VectorSearchEngine(session_factory=_async_session_factory)
    keyword_engine = ElasticsearchNoriEngine(es_url=env.elasticsearch_url)
    reranker = KoreanCrossEncoder()
    hyde_generator = HyDEGenerator(llm=llm)

    # Phase 10: Query Expander
    query_expander = QueryExpander(llm=llm)

    # Phase 11: 멀티쿼리, 질문 분류, 근거 추출, 숫자 검증
    multi_query_generator = MultiQueryGenerator(llm=llm)
    question_classifier = QuestionClassifier()
    evidence_extractor = EvidenceExtractor(llm=llm)
    numeric_verifier = NumericVerifier()

    orchestrator = HybridSearchOrchestrator(
        embedder=embedder,
        vector_engine=vector_engine,
        keyword_engine=keyword_engine,
        reranker=reranker,
        hyde_generator=hyde_generator,
        llm=llm,
        langfuse_monitor=app.state.langfuse_monitor,
        query_expander=query_expander,
        multi_query_generator=multi_query_generator,
        question_classifier=question_classifier,
        evidence_extractor=evidence_extractor,
        numeric_verifier=numeric_verifier,
    )
    search_api.set_orchestrator(orchestrator)

    settings_session = _async_session_factory()
    settings_service = SettingsService(db=settings_session)
    search_api.set_search_settings_service(settings_service)

    # Startup 완료
    app.state.startup_complete = True
    app.state.shutting_down = False
    logger.info("application_started")

    yield

    # --- Graceful Shutdown ---
    app.state.shutting_down = True
    app.state.startup_complete = False
    logger.info("graceful_shutdown_started")

    await asyncio.sleep(1)

    await settings_session.close()
    app.state.langfuse_monitor.flush()

    from app.models.database import get_engine
    engine = get_engine()
    if engine:
        await engine.dispose()
        logger.info("db_engine_disposed")

    logger.info("graceful_shutdown_completed")


app = FastAPI(title="UrstoryRAG", version="0.1.0", lifespan=lifespan)

# CORS — 환경변수 기반 화이트리스트
env = get_settings()
origins = [o.strip() for o in env.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# 보안 헤더
app.add_middleware(SecurityHeadersMiddleware)

# Shutdown 미들웨어
app.add_middleware(ShutdownMiddleware)

# 요청 로깅 미들웨어
app.add_middleware(RequestLoggingMiddleware)

# Rate Limiting
init_limiter()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


def _get_request_id() -> str:
    """미들웨어가 설정한 contextvars에서 request_id를 가져온다."""
    ctx = structlog.contextvars.get_contextvars()
    return ctx.get("request_id", "unknown")


@app.exception_handler(RAGException)
async def rag_exception_handler(request: Request, exc: RAGException):
    request_id = _get_request_id()
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.error_code, "message": str(exc), "request_id": request_id},
        headers={"X-Request-ID": request_id},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = _get_request_id()
    logger.error("unhandled_exception", error=str(exc), request_id=request_id)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_error",
            "message": "내부 오류가 발생했습니다.",
            "request_id": request_id,
        },
        headers={"X-Request-ID": request_id},
    )


# 공개 라우터
app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")

# 인증 필요 라우터
app.include_router(search.router, prefix="/api")
app.include_router(documents.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(watcher.router, prefix="/api")
app.include_router(system.router, prefix="/api")
app.include_router(evaluation.router, prefix="/api")
app.include_router(monitoring.router, prefix="/api")

# 관리자 전용 라우터
app.include_router(admin.router, prefix="/api")
