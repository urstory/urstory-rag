from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings as get_env_settings
from app.models.database import get_db
from app.models.schemas import SettingsResponse, SettingsUpdateRequest
from app.services.settings import SettingsService

router = APIRouter()

_settings_service: SettingsService | None = None


def get_settings_service(db: AsyncSession = Depends(get_db)) -> SettingsService:
    global _settings_service
    if _settings_service is None:
        _settings_service = SettingsService(db)
    _settings_service._db = db
    return _settings_service


@router.get("/settings", response_model=SettingsResponse)
async def get_settings(service: SettingsService = Depends(get_settings_service)):
    settings = await service.get_settings()
    return settings.model_dump()


@router.patch("/settings", response_model=SettingsResponse)
async def patch_settings(
    updates: SettingsUpdateRequest,
    service: SettingsService = Depends(get_settings_service),
):
    updated = await service.update_settings(updates.model_dump(exclude_unset=True))
    return updated.model_dump()


@router.get("/settings/models")
async def get_available_models():
    env = get_env_settings()
    models = {"openai": [], "embedding": []}

    # OpenAI 모델
    if env.openai_api_key:
        models["openai"] = [
            "gpt-4.1",
            "gpt-4.1-mini",
            "gpt-4.1-nano",
            "gpt-4o",
            "gpt-4o-mini",
        ]
        models["embedding"] = [
            "text-embedding-3-small",
            "text-embedding-3-large",
        ]

    return models
