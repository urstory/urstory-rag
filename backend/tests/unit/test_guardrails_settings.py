"""Step 5.7: 가드레일 설정 API 확장 테스트."""
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.settings import get_settings_service
from app.config import RAGSettings
from app.main import app
from app.services.settings import SettingsService


@pytest.mark.asyncio
async def test_guardrail_settings_in_response():
    """GET /api/settings에 가드레일 세부 설정 포함 확인."""
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
        # 가드레일 세부 설정 확인
        assert "guardrails" in data
        g = data["guardrails"]
        assert "pii_detection" in g
        assert "injection_detection" in g
        assert "hallucination_detection" in g
        assert g["pii_detection"]["enabled"] is True
        assert g["injection_detection"]["enabled"] is True
        assert g["hallucination_detection"]["enabled"] is True
        assert g["hallucination_detection"]["threshold"] == 0.8
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_guardrail_settings_update():
    """PATCH /api/settings 가드레일 설정 변경."""
    updated = RAGSettings()
    updated.guardrails.pii_detection.enabled = False

    mock_service = AsyncMock(spec=SettingsService)
    mock_service.update_settings.return_value = updated

    app.dependency_overrides[get_settings_service] = lambda: mock_service
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.patch(
                "/api/settings",
                json={
                    "guardrails": {
                        "pii_detection": {"enabled": False},
                    }
                },
            )

        assert response.status_code == 200
        data = response.json()
        assert data["guardrails"]["pii_detection"]["enabled"] is False
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_guardrail_individual_toggle():
    """개별 가드레일 ON/OFF 확인."""
    settings = RAGSettings()
    # 기본값 확인
    assert settings.guardrails.pii_detection.enabled is True
    assert settings.guardrails.injection_detection.enabled is True
    assert settings.guardrails.hallucination_detection.enabled is True

    # 개별 토글
    settings.guardrails.pii_detection.enabled = False
    assert settings.guardrails.pii_detection.enabled is False
    assert settings.guardrails.injection_detection.enabled is True  # 다른 것은 변하지 않음


@pytest.mark.asyncio
async def test_guardrail_pii_patterns():
    """PII 탐지 패턴 설정."""
    settings = RAGSettings()
    assert "주민등록번호" in settings.guardrails.pii_detection.patterns
    assert "휴대전화" in settings.guardrails.pii_detection.patterns


@pytest.mark.asyncio
async def test_guardrail_hallucination_threshold():
    """할루시네이션 threshold 설정."""
    settings = RAGSettings()
    assert settings.guardrails.hallucination_detection.threshold == 0.8

    settings.guardrails.hallucination_detection.threshold = 0.6
    assert settings.guardrails.hallucination_detection.threshold == 0.6


@pytest.mark.asyncio
async def test_backward_compat_flat_flags():
    """기존 플랫 불리언 플래그와 호환성 유지."""
    settings = RAGSettings()
    # 플랫 플래그는 guardrails 서브모델과 동기화
    assert settings.pii_detection_enabled == settings.guardrails.pii_detection.enabled
    assert settings.injection_detection_enabled == settings.guardrails.injection_detection.enabled
    assert settings.hallucination_detection_enabled == settings.guardrails.hallucination_detection.enabled
