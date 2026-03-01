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

    yield

    # 종료 시 flush
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
