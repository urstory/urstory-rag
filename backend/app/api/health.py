import importlib.metadata

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.config import get_settings

router = APIRouter()


def _get_version() -> str:
    try:
        return importlib.metadata.version("urstory-rag")
    except importlib.metadata.PackageNotFoundError:
        return "dev"


async def check_db() -> bool:
    """PostgreSQL SELECT 1 실행."""
    try:
        from app.models.database import get_engine

        engine = get_engine()
        if engine is None:
            return False
        from sqlalchemy import text

        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def check_elasticsearch() -> bool:
    """Elasticsearch GET / 호출."""
    try:
        settings = get_settings()
        async with httpx.AsyncClient() as client:
            resp = await client.get(settings.elasticsearch_url, timeout=5.0)
            return resp.status_code == 200
    except Exception:
        return False


async def check_openai() -> bool:
    """OpenAI API 키 유효성 확인."""
    try:
        settings = get_settings()
        if not settings.openai_api_key:
            return False
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                timeout=5.0,
            )
            return resp.status_code == 200
    except Exception:
        return False


async def check_redis() -> bool:
    """Redis PING."""
    try:
        import redis.asyncio as aioredis

        settings = get_settings()
        r = aioredis.from_url(settings.redis_url)
        await r.ping()
        await r.aclose()
        return True
    except Exception:
        return False


@router.get("/health")
async def health_check():
    """전체 시스템 상태 (관리자 대시보드용)."""
    db_ok = await check_db()
    es_ok = await check_elasticsearch()
    openai_ok = await check_openai()
    redis_ok = await check_redis()

    required_ok = db_ok and es_ok and redis_ok

    # Circuit Breaker 상태 수집
    circuit_breakers = _collect_circuit_breaker_stats()

    return {
        "status": "ok" if required_ok else "degraded",
        "version": _get_version(),
        "circuit_breakers": circuit_breakers,
        "components": {
            "database": {
                "status": "connected" if db_ok else "disconnected",
                "required": True,
                "description": "PostgreSQL + PGVector (문서/벡터 저장소)",
                "impact": "disconnected 시 모든 기능 비활성화",
            },
            "elasticsearch": {
                "status": "connected" if es_ok else "disconnected",
                "required": True,
                "description": "Elasticsearch + Nori (키워드 검색)",
                "impact": "disconnected 시 키워드 검색 비활성화",
            },
            "redis": {
                "status": "connected" if redis_ok else "disconnected",
                "required": True,
                "description": "Redis (세션, 작업 큐, 토큰 블랙리스트)",
                "impact": "disconnected 시 로그인/로그아웃 장애 가능",
            },
            "openai": {
                "status": "connected" if openai_ok else "disconnected",
                "required": False,
                "description": "OpenAI API (임베딩, LLM 생성, 평가)",
                "impact": "disconnected 시 검색/답변 생성 불가 (기존 인덱스 검색은 가능)",
            },
        },
    }


def _collect_circuit_breaker_stats() -> list[dict]:
    """앱에 등록된 Circuit Breaker 상태를 수집한다."""
    stats = []
    try:
        from app.main import app as main_app
        orchestrator = getattr(main_app.state, "search_orchestrator", None)
        if orchestrator is None:
            return stats
        embedder = getattr(orchestrator, "embedder", None)
        llm = getattr(orchestrator, "llm", None)
        if embedder and hasattr(embedder, "_circuit_breaker"):
            stats.append(embedder._circuit_breaker.stats())
        if llm and hasattr(llm, "_circuit_breaker"):
            stats.append(llm._circuit_breaker.stats())
    except Exception:
        pass
    return stats


@router.get("/health/live")
async def liveness():
    """Liveness Probe — 프로세스 생존 확인."""
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness():
    """Readiness Probe — DB, ES, Redis 연결 확인."""
    db_ok = await check_db()
    es_ok = await check_elasticsearch()
    redis_ok = await check_redis()

    all_ok = db_ok and es_ok and redis_ok
    status_code = 200 if all_ok else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if all_ok else "not_ready",
            "components": {
                "database": "ok" if db_ok else "fail",
                "elasticsearch": "ok" if es_ok else "fail",
                "redis": "ok" if redis_ok else "fail",
            },
        },
    )


@router.get("/health/startup")
async def startup_check(request: Request):
    """Startup Probe — 초기화 완료 확인."""
    ready = getattr(request.app.state, "startup_complete", False)
    return JSONResponse(
        status_code=200 if ready else 503,
        content={"status": "started" if ready else "starting"},
    )
