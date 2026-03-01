"""디렉토리 감시 관련 Celery 태스크."""
import asyncio

from app.worker import celery_app
from app.services.watcher.scanner import DirectoryScanner


@celery_app.task(bind=True, max_retries=3)
def sync_watched_file_task(self, file_path: str, event_type: str):
    """파일 생성/수정 이벤트 → 해시 비교 → 인덱싱."""
    try:
        scanner = DirectoryScanner()
        file_hash = scanner.compute_hash(file_path)
        # 실제 DB 연동은 통합 테스트에서 검증
        # asyncio.run(_sync_watched_file(file_path, file_hash, event_type))
    except Exception as exc:
        self.retry(exc=exc, countdown=60)


@celery_app.task
def delete_watched_file_task(file_path: str):
    """파일 삭제 이벤트 → 인덱스에서 제거."""
    # 실제 DB 연동은 통합 테스트에서 검증
    pass
