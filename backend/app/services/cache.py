"""Redis 캐싱 서비스."""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from app.redis import get_redis

logger = logging.getLogger(__name__)

# 캐시 키 접두사
PREFIX_SEARCH = "cache:search:"
PREFIX_SETTINGS = "cache:settings"
PREFIX_STATS = "cache:stats"


class CacheService:
    """Redis 기반 캐싱 서비스."""

    def __init__(self, default_ttl: int = 3600, enabled: bool = True) -> None:
        self._default_ttl = default_ttl
        self._enabled = enabled
        self._hits = 0
        self._misses = 0

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    @property
    def default_ttl(self) -> int:
        return self._default_ttl

    @default_ttl.setter
    def default_ttl(self, value: int) -> None:
        self._default_ttl = value

    # --- 검색 캐시 ---

    def _make_search_key(self, query: str, settings_hash: str) -> str:
        """쿼리 + 설정 해시로 캐시 키 생성."""
        raw = f"{query}|{settings_hash}"
        digest = hashlib.sha256(raw.encode()).hexdigest()
        return f"{PREFIX_SEARCH}{digest}"

    @staticmethod
    def compute_settings_hash(settings: dict) -> str:
        """검색에 영향을 주는 설정 필드만 추출하여 해시."""
        relevant_keys = [
            "search_mode", "hyde_enabled", "reranking_enabled",
            "multi_query_enabled", "reranker_top_k", "retriever_top_k",
            "vector_weight", "keyword_weight", "rrf_constant",
            "embedding_model", "llm_model", "llm_temperature",
            "cascading_bm25_threshold", "query_expansion_enabled",
            "document_scope_enabled", "exact_citation_enabled",
        ]
        subset = {k: settings.get(k) for k in relevant_keys if k in settings}
        raw = json.dumps(subset, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    async def get_search(self, query: str, settings_hash: str) -> dict | None:
        """검색 캐시 조회. 캐시 미스 시 None."""
        if not self._enabled:
            return None
        try:
            r = await get_redis()
            key = self._make_search_key(query, settings_hash)
            data = await r.get(key)
            if data is not None:
                self._hits += 1
                logger.debug("cache_hit", extra={"key_prefix": "search"})
                return json.loads(data)
            self._misses += 1
            return None
        except Exception:
            logger.warning("cache_get_failed", exc_info=True)
            self._misses += 1
            return None

    async def set_search(
        self, query: str, settings_hash: str, value: dict, ttl: int | None = None,
    ) -> None:
        """검색 결과를 캐시에 저장."""
        if not self._enabled:
            return
        try:
            r = await get_redis()
            key = self._make_search_key(query, settings_hash)
            await r.setex(key, ttl or self._default_ttl, json.dumps(value, default=str))
        except Exception:
            logger.warning("cache_set_failed", exc_info=True)

    # --- 범용 캐시 ---

    async def get(self, key: str) -> Any | None:
        """단순 키-값 캐시 조회."""
        if not self._enabled:
            return None
        try:
            r = await get_redis()
            data = await r.get(key)
            if data is not None:
                self._hits += 1
                return json.loads(data)
            self._misses += 1
            return None
        except Exception:
            logger.warning("cache_get_failed", exc_info=True)
            return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """단순 키-값 캐시 저장."""
        if not self._enabled:
            return
        try:
            r = await get_redis()
            await r.setex(key, ttl or self._default_ttl, json.dumps(value, default=str))
        except Exception:
            logger.warning("cache_set_failed", exc_info=True)

    # --- 무효화 ---

    async def invalidate_search(self) -> int:
        """검색 캐시 전체 무효화. 삭제된 키 수 반환."""
        return await self._delete_by_pattern(f"{PREFIX_SEARCH}*")

    async def invalidate_settings(self) -> None:
        """설정 캐시 무효화."""
        try:
            r = await get_redis()
            await r.delete(PREFIX_SETTINGS)
        except Exception:
            logger.warning("cache_invalidate_failed", exc_info=True)

    async def invalidate_stats(self) -> None:
        """통계 캐시 무효화."""
        try:
            r = await get_redis()
            await r.delete(PREFIX_STATS)
        except Exception:
            logger.warning("cache_invalidate_failed", exc_info=True)

    async def invalidate_all(self) -> int:
        """모든 캐시 무효화. 삭제된 키 수 반환."""
        count = await self._delete_by_pattern("cache:*")
        self._hits = 0
        self._misses = 0
        return count

    async def _delete_by_pattern(self, pattern: str) -> int:
        """SCAN으로 패턴 매칭 키 삭제. KEYS 명령 사용 금지."""
        try:
            r = await get_redis()
            count = 0
            async for key in r.scan_iter(match=pattern, count=100):
                await r.delete(key)
                count += 1
            return count
        except Exception:
            logger.warning("cache_pattern_delete_failed", exc_info=True)
            return 0

    # --- 메트릭 ---

    def get_metrics(self) -> dict:
        """인메모리 히트/미스 카운터."""
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / total, 4) if total > 0 else 0.0,
            "total_requests": total,
        }

    async def get_redis_info(self) -> dict:
        """Redis INFO에서 캐시 관련 정보 추출."""
        try:
            r = await get_redis()
            info = await r.info("memory")
            key_count = 0
            async for _ in r.scan_iter(match="cache:*", count=100):
                key_count += 1
            return {
                "cache_key_count": key_count,
                "used_memory_human": info.get("used_memory_human", "N/A"),
                "used_memory_bytes": info.get("used_memory", 0),
            }
        except Exception:
            logger.warning("cache_info_failed", exc_info=True)
            return {"cache_key_count": 0, "used_memory_human": "N/A", "used_memory_bytes": 0}
