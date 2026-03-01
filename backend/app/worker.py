"""Celery 앱 초기화."""
from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "rag",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.indexing"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Seoul",
    enable_utc=True,
)
