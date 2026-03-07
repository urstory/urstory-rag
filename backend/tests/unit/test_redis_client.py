"""Step 1 RED: 공용 Redis 클라이언트 단위 테스트."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio


class TestGetRedis:
    """get_redis() 함수 테스트."""

    @pytest.mark.asyncio
    async def test_get_redis_returns_client(self):
        """get_redis()가 Redis 객체를 반환한다."""
        import app.redis as redis_mod
        redis_mod._pool = None  # 상태 초기화

        mock_pool = MagicMock()
        with patch("app.redis.aioredis.ConnectionPool") as MockPool:
            MockPool.from_url.return_value = mock_pool
            r = await redis_mod.get_redis()

        assert r is not None
        MockPool.from_url.assert_called_once()
        redis_mod._pool = None

    @pytest.mark.asyncio
    async def test_get_redis_reuses_pool(self):
        """두 번 호출 시 동일 풀을 재사용한다."""
        import app.redis as redis_mod
        redis_mod._pool = None

        mock_pool = MagicMock()
        with patch("app.redis.aioredis.ConnectionPool") as MockPool:
            MockPool.from_url.return_value = mock_pool
            r1 = await redis_mod.get_redis()
            r2 = await redis_mod.get_redis()

        # ConnectionPool.from_url은 1번만 호출
        assert MockPool.from_url.call_count == 1
        redis_mod._pool = None

    @pytest.mark.asyncio
    async def test_close_redis_disconnects(self):
        """close_redis() 호출 후 풀이 None이 된다."""
        import app.redis as redis_mod

        mock_pool = AsyncMock()
        redis_mod._pool = mock_pool

        await redis_mod.close_redis()

        assert redis_mod._pool is None
        mock_pool.disconnect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_redis_noop_when_no_pool(self):
        """풀이 없을 때 close_redis()는 에러 없이 통과한다."""
        import app.redis as redis_mod
        redis_mod._pool = None

        await redis_mod.close_redis()  # 에러 없이 통과
        assert redis_mod._pool is None
