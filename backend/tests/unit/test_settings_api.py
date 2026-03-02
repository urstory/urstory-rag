"""Step 2.8 RED: 설정 API 테스트."""
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.settings import get_settings_service
from app.config import RAGSettings
from app.main import app
from app.services.settings import SettingsService


@pytest.mark.asyncio
async def test_get_default_settings():
    """초기 상태에서 기본 설정 반환 확인."""
    mock_service = AsyncMock(spec=SettingsService)
    mock_service.get_settings.return_value = RAGSettings()

    app.dependency_overrides[get_settings_service] = lambda: mock_service
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/settings")

        assert response.status_code == 200
        data = response.json()
        assert data["chunking_strategy"] == "auto"
        assert data["chunk_size"] == 1024
        assert data["reranking_enabled"] is True
        assert data["reranker_model"] == "dragonkue/bge-reranker-v2-m3-ko"
        assert data["hyde_enabled"] is True
        assert data["llm_provider"] == "openai"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_patch_settings():
    """부분 업데이트 후 변경 확인."""
    updated = RAGSettings(chunk_size=1024, reranking_enabled=False)

    mock_service = AsyncMock(spec=SettingsService)
    mock_service.update_settings.return_value = updated

    app.dependency_overrides[get_settings_service] = lambda: mock_service
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.patch(
                "/api/settings",
                json={"chunk_size": 1024, "reranking_enabled": False},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["chunk_size"] == 1024
        assert data["reranking_enabled"] is False
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_settings_cache_invalidation():
    """업데이트 후 캐시 반영 확인."""
    service = SettingsService.__new__(SettingsService)
    service._db = None
    service._cache = RAGSettings()
    service._cache_time = 9999999999.0  # 미래 (캐시 유효)

    # 캐시된 설정 반환 확인
    with patch.object(service, "_load_from_db", new_callable=AsyncMock) as mock_load:
        result = await service.get_settings()
        mock_load.assert_not_called()  # 캐시 사용, DB 미호출

    # 업데이트 시 캐시 무효화 확인
    with patch.object(service, "_save_to_db", new_callable=AsyncMock):
        await service.update_settings({"chunk_size": 2048})
        assert service._cache is None  # 캐시 무효화됨
