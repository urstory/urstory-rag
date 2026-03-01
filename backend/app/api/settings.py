import httpx
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
    models = {"ollama": [], "api": []}

    # Ollama 모델 조회
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{env.ollama_url}/api/tags", timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                models["ollama"] = [m["name"] for m in data.get("models", [])]
    except Exception:
        pass

    # API 모델
    if env.openai_api_key:
        models["api"].append("gpt-4")
        models["api"].append("gpt-4o")
        models["api"].append("gpt-4o-mini")
    if env.anthropic_api_key:
        models["api"].append("claude-sonnet-4-6")
        models["api"].append("claude-haiku-4-5")

    return models
