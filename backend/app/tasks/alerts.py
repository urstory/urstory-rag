"""이상 탐지 알림 Celery 태스크."""
import asyncio

from app.worker import celery_app


@celery_app.task(name="check_alerts")
def check_alerts_task():
    """주기적으로 이상 탐지 체크를 실행한다."""
    asyncio.run(_run_checks())


async def _run_checks():
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.config import get_settings
    from app.monitoring.alerts import AlertChecker

    env = get_settings()
    engine = create_async_engine(env.database_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as db:
        checker = AlertChecker(db=db)
        alerts = await checker.run_all_checks()
        if alerts:
            # TODO: 향후 이메일/슬랙 알림 연동
            import logging
            logger = logging.getLogger(__name__)
            for alert in alerts:
                logger.warning("Alert: %s", alert["message"])

    await engine.dispose()
