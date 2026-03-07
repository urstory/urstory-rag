"""Step 4 RED: 설정 서비스 Redis 캐시 테스트."""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from app.config import RAGSettings
from app.services.cache import CacheService, PREFIX_SETTINGS
from app.services.settings import SettingsService


@pytest.fixture
def mock_cache():
    m = AsyncMock(spec=CacheService)
    m.get = AsyncMock(return_value=None)
    m.set = AsyncMock()
    m.invalidate_settings = AsyncMock()
    m.invalidate_search = AsyncMock()
    return m


@pytest.fixture
def mock_db():
    """Mock AsyncSession."""
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    db.add = MagicMock()
    return db


class TestSettingsInMemoryCache:

    @pytest.mark.asyncio
    async def test_settings_inmemory_cache_hit(self, mock_db, mock_cache):
        """인메모리 캐시 60초 내 DB 미조회."""
        svc = SettingsService(db=mock_db, cache=mock_cache)

        # 첫 호출: DB 조회
        s1 = await svc.get_settings()
        assert mock_db.execute.call_count == 1

        # 두 번째 호출: 인메모리 캐시 히트 → DB 미조회
        s2 = await svc.get_settings()
        assert mock_db.execute.call_count == 1  # 여전히 1번
        assert s1 == s2


class TestSettingsRedisCache:

    @pytest.mark.asyncio
    async def test_settings_redis_cache_hit(self, mock_db, mock_cache):
        """인메모리 만료 후 Redis에서 복원."""
        svc = SettingsService(db=mock_db, cache=mock_cache)

        # 인메모리 캐시 만료 시뮬레이션
        svc._local_cache = None
        svc._cache_time = 0.0

        # Redis에 설정값이 있다면
        mock_cache.get.return_value = RAGSettings().model_dump()

        settings = await svc.get_settings()

        mock_cache.get.assert_awaited_once()
        # DB는 조회하지 않아야 함
        mock_db.execute.assert_not_awaited()
        assert settings.search_mode == "hybrid"  # 기본값 확인


class TestSettingsUpdateInvalidation:

    @pytest.mark.asyncio
    async def test_settings_update_invalidates_both(self, mock_db, mock_cache):
        """설정 변경 시 인메모리 + Redis + 검색 캐시 무효화."""
        svc = SettingsService(db=mock_db, cache=mock_cache)

        # 먼저 로드
        await svc.get_settings()

        # 업데이트
        await svc.update_settings({"search_mode": "vector"})

        # 인메모리 캐시가 클리어됨
        assert svc._local_cache is None

        # Redis 캐시도 무효화
        mock_cache.invalidate_settings.assert_awaited_once()
        mock_cache.invalidate_search.assert_awaited_once()
