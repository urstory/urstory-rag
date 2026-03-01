"""Step 6.7 RED: 이상 탐지 알림 단위 테스트."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.database import Base

TEST_DATABASE_URL = "postgresql+asyncpg://admin:changeme_strong_password@localhost:5432/shared_test"


@pytest_asyncio.fixture
async def alert_db():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


class TestAlertChecker:
    """이상 탐지 알림 테스트."""

    @pytest.mark.asyncio
    async def test_alert_triggered_when_low_hallucination(self, alert_db):
        """평균 할루시네이션 0.7 미만 시 알림 생성."""
        from app.monitoring.alerts import AlertChecker

        checker = AlertChecker(db=alert_db)

        # 낮은 할루시네이션 점수 mock
        with patch.object(
            checker, "_get_recent_hallucination_scores",
            new_callable=AsyncMock,
            return_value=[0.5, 0.6, 0.4],
        ):
            alerts = await checker.check_hallucination_rate()

        assert len(alerts) == 1
        assert "할루시네이션" in alerts[0]["message"]

    @pytest.mark.asyncio
    async def test_no_alert_when_normal(self, alert_db):
        """정상 범위 시 알림 없음."""
        from app.monitoring.alerts import AlertChecker

        checker = AlertChecker(db=alert_db)

        with patch.object(
            checker, "_get_recent_hallucination_scores",
            new_callable=AsyncMock,
            return_value=[0.9, 0.85, 0.95],
        ):
            alerts = await checker.check_hallucination_rate()

        assert len(alerts) == 0

    @pytest.mark.asyncio
    async def test_no_alert_when_no_data(self, alert_db):
        """데이터 없을 때 알림 없음."""
        from app.monitoring.alerts import AlertChecker

        checker = AlertChecker(db=alert_db)

        with patch.object(
            checker, "_get_recent_hallucination_scores",
            new_callable=AsyncMock,
            return_value=[],
        ):
            alerts = await checker.check_hallucination_rate()

        assert len(alerts) == 0

    @pytest.mark.asyncio
    async def test_check_error_rate_high(self, alert_db):
        """에러율 높을 때 알림 생성."""
        from app.monitoring.alerts import AlertChecker

        checker = AlertChecker(db=alert_db)

        with patch.object(
            checker, "_get_recent_error_rate",
            new_callable=AsyncMock,
            return_value=0.15,  # 15% 에러율
        ):
            alerts = await checker.check_error_rate()

        assert len(alerts) == 1
        assert "에러" in alerts[0]["message"]

    @pytest.mark.asyncio
    async def test_check_error_rate_normal(self, alert_db):
        """에러율 정상일 때 알림 없음."""
        from app.monitoring.alerts import AlertChecker

        checker = AlertChecker(db=alert_db)

        with patch.object(
            checker, "_get_recent_error_rate",
            new_callable=AsyncMock,
            return_value=0.02,
        ):
            alerts = await checker.check_error_rate()

        assert len(alerts) == 0

    @pytest.mark.asyncio
    async def test_run_all_checks(self, alert_db):
        """모든 체크를 한번에 실행."""
        from app.monitoring.alerts import AlertChecker

        checker = AlertChecker(db=alert_db)

        with (
            patch.object(
                checker, "_get_recent_hallucination_scores",
                new_callable=AsyncMock,
                return_value=[0.9, 0.85],
            ),
            patch.object(
                checker, "_get_recent_error_rate",
                new_callable=AsyncMock,
                return_value=0.01,
            ),
        ):
            alerts = await checker.run_all_checks()

        assert len(alerts) == 0
