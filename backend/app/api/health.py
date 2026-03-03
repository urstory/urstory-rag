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
    db_ok = await check_db()
    es_ok = await check_elasticsearch()
    openai_ok = await check_openai()
    redis_ok = await check_redis()

    return {
        "status": "ok",
        "components": {
            "database": "connected" if db_ok else "disconnected",
            "elasticsearch": "connected" if es_ok else "disconnected",
            "openai": "connected" if openai_ok else "disconnected",
            "redis": "connected" if redis_ok else "disconnected",
        },
    }
