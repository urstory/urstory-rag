import httpx
from fastapi import APIRouter

from app.config import get_settings

router = APIRouter()


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


async def check_ollama() -> bool:
    """Ollama GET /api/tags 호출."""
    try:
        settings = get_settings()
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{settings.ollama_url}/api/tags", timeout=5.0)
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
    db_ok = await check_db()
    es_ok = await check_elasticsearch()
    ollama_ok = await check_ollama()
    redis_ok = await check_redis()

    return {
        "status": "ok",
        "components": {
            "database": "connected" if db_ok else "disconnected",
            "elasticsearch": "connected" if es_ok else "disconnected",
            "ollama": "connected" if ollama_ok else "disconnected",
            "redis": "connected" if redis_ok else "disconnected",
        },
    }
