from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.cache import CacheService

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import RAGSettings
from app.models.database import Setting

CACHE_TTL = 60.0  # 60초


class SettingsService:
    def __init__(self, db: AsyncSession | None = None, cache: "CacheService | None" = None):
        self._db = db
        self._cache_svc = cache
        self._local_cache: RAGSettings | None = None
        self._cache_time: float = 0.0

    async def get_settings(self) -> RAGSettings:
        # 1차: 인메모리 캐시
        if self._local_cache is not None and (time.time() - self._cache_time) < CACHE_TTL:
            return self._local_cache

        # 2차: Redis 캐시
        if self._cache_svc:
            from app.services.cache import PREFIX_SETTINGS
            cached = await self._cache_svc.get(PREFIX_SETTINGS)
            if cached is not None:
                self._local_cache = RAGSettings(**cached)
                self._cache_time = time.time()
                return self._local_cache

        # 3차: DB 조회
        settings = await self._load_from_db()
        self._local_cache = settings
        self._cache_time = time.time()

        # Redis에 저장
        if self._cache_svc:
            from app.services.cache import PREFIX_SETTINGS
            await self._cache_svc.set(PREFIX_SETTINGS, settings.model_dump(), ttl=60)

        return settings

    async def update_settings(self, updates: dict) -> RAGSettings:
        current = await self.get_settings()
        updated_data = current.model_dump()
        updated_data.update({k: v for k, v in updates.items() if v is not None})
        updated = RAGSettings(**updated_data)

        await self._save_to_db(updated)

        # 캐시 무효화
        self._local_cache = None
        if self._cache_svc:
            await self._cache_svc.invalidate_settings()
            await self._cache_svc.invalidate_search()  # 설정 변경 → 검색 캐시도 무효화

        return updated

    async def _load_from_db(self) -> RAGSettings:
        if self._db is None:
            return RAGSettings()

        try:
            result = await self._db.execute(
                select(Setting).where(Setting.key == "rag_settings")
            )
            row = result.scalar_one_or_none()
            if row is None:
                return RAGSettings()
            return RAGSettings(**row.value)
        except Exception:
            return RAGSettings()

    async def _save_to_db(self, settings: RAGSettings) -> None:
        if self._db is None:
            return

        result = await self._db.execute(
            select(Setting).where(Setting.key == "rag_settings")
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = Setting(key="rag_settings", value=settings.model_dump())
            self._db.add(row)
        else:
            row.value = settings.model_dump()

        await self._db.commit()
