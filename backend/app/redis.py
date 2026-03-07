"""공용 Redis 비동기 클라이언트."""
from __future__ import annotations

import redis.asyncio as aioredis

from app.config import get_settings

_pool: aioredis.ConnectionPool | None = None


async def get_redis() -> aioredis.Redis:
    """공용 Redis 클라이언트를 반환한다. ConnectionPool을 재사용."""
    global _pool
    if _pool is None:
        env = get_settings()
        _pool = aioredis.ConnectionPool.from_url(
            env.redis_url,
            decode_responses=True,
            max_connections=20,
        )
    return aioredis.Redis(connection_pool=_pool)


async def close_redis() -> None:
    """앱 종료 시 커넥션 풀 정리."""
    global _pool
    if _pool is not None:
        await _pool.disconnect()
        _pool = None
