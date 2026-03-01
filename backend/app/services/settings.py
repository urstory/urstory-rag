import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import RAGSettings
from app.models.database import Setting

CACHE_TTL = 60.0  # 60초


class SettingsService:
    def __init__(self, db: AsyncSession | None = None):
        self._db = db
        self._cache: RAGSettings | None = None
        self._cache_time: float = 0.0

    async def get_settings(self) -> RAGSettings:
        if self._cache is not None and (time.time() - self._cache_time) < CACHE_TTL:
            return self._cache

        settings = await self._load_from_db()
        self._cache = settings
        self._cache_time = time.time()
        return settings

    async def update_settings(self, updates: dict) -> RAGSettings:
        current = await self.get_settings()
        updated_data = current.model_dump()
        updated_data.update({k: v for k, v in updates.items() if v is not None})
        updated = RAGSettings(**updated_data)

        await self._save_to_db(updated)
        self._cache = None  # 캐시 무효화
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
