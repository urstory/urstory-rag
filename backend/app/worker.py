"""Celery 앱 초기화."""
from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "rag",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.indexing", "app.tasks.evaluation", "app.tasks.alerts"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Seoul",
    enable_utc=True,
    beat_schedule={
        "check-alerts-hourly": {
            "task": "check_alerts",
            "schedule": crontab(minute=0),  # 매시 정각
        },
    },
)
