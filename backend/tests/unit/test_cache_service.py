"""Step 2 RED: 캐시 서비스 단위 테스트."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.cache import CacheService, PREFIX_SEARCH


@pytest.fixture
def mock_redis():
    """Mock Redis 클라이언트."""
    r = AsyncMock()
    r.get = AsyncMock(return_value=None)
    r.setex = AsyncMock()
    r.delete = AsyncMock()
    r.info = AsyncMock(return_value={"used_memory_human": "1.5M", "used_memory": 1572864})
    r.scan_iter = MagicMock()  # async generator는 별도 설정

    async def empty_scan(*args, **kwargs):
        return
        yield  # noqa: unreachable — makes this an async generator

    r.scan_iter.return_value = empty_scan()
    return r


@pytest.fixture
def cache(mock_redis):
    """CacheService with mocked Redis."""
    with patch("app.services.cache.get_redis", return_value=mock_redis):
        svc = CacheService(default_ttl=3600, enabled=True)
    return svc


class TestSearchKey:
    """캐시 키 생성 테스트."""

    def test_make_search_key_deterministic(self):
        """동일 입력 → 동일 키."""
        svc = CacheService()
        k1 = svc._make_search_key("hello", "abc")
        k2 = svc._make_search_key("hello", "abc")
        assert k1 == k2
        assert k1.startswith(PREFIX_SEARCH)

    def test_make_search_key_different_query(self):
        """다른 쿼리 → 다른 키."""
        svc = CacheService()
        k1 = svc._make_search_key("hello", "abc")
        k2 = svc._make_search_key("world", "abc")
        assert k1 != k2

    def test_make_search_key_different_settings(self):
        """다른 설정 해시 → 다른 키."""
        svc = CacheService()
        k1 = svc._make_search_key("hello", "abc")
        k2 = svc._make_search_key("hello", "def")
        assert k1 != k2


class TestComputeSettingsHash:
    """설정 해시 테스트."""

    def test_compute_settings_hash_ignores_irrelevant(self):
        """관련 없는 필드 변경 시 동일 해시."""
        s1 = {"search_mode": "hybrid", "llm_temperature": 0.3, "system_prompt": "abc"}
        s2 = {"search_mode": "hybrid", "llm_temperature": 0.3, "system_prompt": "xyz"}
        assert CacheService.compute_settings_hash(s1) == CacheService.compute_settings_hash(s2)

    def test_compute_settings_hash_detects_relevant(self):
        """관련 필드 변경 시 다른 해시."""
        s1 = {"search_mode": "hybrid", "hyde_enabled": True}
        s2 = {"search_mode": "hybrid", "hyde_enabled": False}
        assert CacheService.compute_settings_hash(s1) != CacheService.compute_settings_hash(s2)


class TestSearchCache:
    """검색 캐시 조회/저장 테스트."""

    @pytest.mark.asyncio
    async def test_get_search_miss(self, mock_redis):
        """캐시 없을 때 None 반환."""
        mock_redis.get.return_value = None
        with patch("app.services.cache.get_redis", AsyncMock(return_value=mock_redis)):
            svc = CacheService(default_ttl=3600, enabled=True)
            result = await svc.get_search("test query", "hash123")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_and_get_search(self, mock_redis):
        """set 후 get 성공."""
        stored = {"query": "test", "answer": "result"}
        mock_redis.get.return_value = json.dumps(stored)

        with patch("app.services.cache.get_redis", AsyncMock(return_value=mock_redis)):
            svc = CacheService(default_ttl=3600, enabled=True)
            await svc.set_search("test", "hash", stored, ttl=300)
            result = await svc.get_search("test", "hash")

        assert result == stored
        mock_redis.setex.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_disabled_cache_returns_none(self, mock_redis):
        """enabled=False 시 항상 None."""
        with patch("app.services.cache.get_redis", AsyncMock(return_value=mock_redis)):
            svc = CacheService(default_ttl=3600, enabled=False)
            await svc.set_search("test", "hash", {"data": 1})
            result = await svc.get_search("test", "hash")

        assert result is None
        mock_redis.get.assert_not_awaited()
        mock_redis.setex.assert_not_awaited()


class TestInvalidation:
    """캐시 무효화 테스트."""

    @pytest.mark.asyncio
    async def test_invalidate_search(self, mock_redis):
        """검색 캐시 무효화."""
        keys = [f"{PREFIX_SEARCH}key1", f"{PREFIX_SEARCH}key2"]

        async def scan_keys(*args, **kwargs):
            for k in keys:
                yield k

        mock_redis.scan_iter.return_value = scan_keys()

        with patch("app.services.cache.get_redis", AsyncMock(return_value=mock_redis)):
            svc = CacheService(default_ttl=3600, enabled=True)
            count = await svc.invalidate_search()

        assert count == 2

    @pytest.mark.asyncio
    async def test_invalidate_all(self, mock_redis):
        """전체 무효화."""
        keys = ["cache:search:a", "cache:settings", "cache:stats"]

        async def scan_keys(*args, **kwargs):
            for k in keys:
                yield k

        mock_redis.scan_iter.return_value = scan_keys()

        with patch("app.services.cache.get_redis", AsyncMock(return_value=mock_redis)):
            svc = CacheService(default_ttl=3600, enabled=True)
            # 먼저 히트 카운터를 올려놓고
            svc._hits = 5
            svc._misses = 3
            count = await svc.invalidate_all()

        assert count == 3
        # 메트릭 초기화 확인
        assert svc._hits == 0
        assert svc._misses == 0


class TestMetrics:
    """메트릭 테스트."""

    def test_get_metrics(self):
        """히트/미스 카운터 정확성."""
        svc = CacheService()
        svc._hits = 8
        svc._misses = 2

        metrics = svc.get_metrics()
        assert metrics["hits"] == 8
        assert metrics["misses"] == 2
        assert metrics["hit_rate"] == 0.8
        assert metrics["total_requests"] == 10

    def test_get_metrics_zero_requests(self):
        """요청 0건일 때 hit_rate는 0."""
        svc = CacheService()
        metrics = svc.get_metrics()
        assert metrics["hit_rate"] == 0.0


class TestGracefulDegradation:
    """Redis 장애 시 graceful degradation."""

    @pytest.mark.asyncio
    async def test_cache_graceful_on_redis_error(self):
        """Redis 장애 시 None 반환 (예외 전파 안 함)."""
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = ConnectionError("Redis down")

        with patch("app.services.cache.get_redis", AsyncMock(return_value=mock_redis)):
            svc = CacheService(default_ttl=3600, enabled=True)
            result = await svc.get_search("test", "hash")

        assert result is None

    @pytest.mark.asyncio
    async def test_cache_set_graceful_on_redis_error(self):
        """Redis 장애 시 set도 조용히 실패."""
        mock_redis = AsyncMock()
        mock_redis.setex.side_effect = ConnectionError("Redis down")

        with patch("app.services.cache.get_redis", AsyncMock(return_value=mock_redis)):
            svc = CacheService(default_ttl=3600, enabled=True)
            # 에러 없이 통과
            await svc.set_search("test", "hash", {"data": 1})
