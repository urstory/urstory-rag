"""watchdog 이벤트 핸들러: 지원 파일 변경 감지."""
from pathlib import Path

from watchdog.events import FileSystemEventHandler


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}


def _lazy_import_task():
    """Celery 태스크 지연 import (순환 참조 방지)."""
    from app.tasks.watcher import sync_watched_file_task, delete_watched_file_task
    return sync_watched_file_task, delete_watched_file_task


# 모듈 레벨에서 지연 import를 위한 래퍼
class _TaskProxy:
    """테스트에서 패치 가능하도록 모듈 레벨 참조."""
    pass


try:
    from app.tasks.watcher import sync_watched_file_task, delete_watched_file_task
except ImportError:
    sync_watched_file_task = None
    delete_watched_file_task = None


class DocumentFileHandler(FileSystemEventHandler):
    """지원 파일(PDF, DOCX, TXT, MD) 변경 이벤트 처리."""

    def _is_supported(self, path: str) -> bool:
        p = Path(path)
        if str(path).endswith("/"):
            return False
        return p.suffix.lower() in SUPPORTED_EXTENSIONS

    def on_created(self, event):
        if event.is_directory:
            return
        if self._is_supported(event.src_path):
            self._dispatch_sync(event.src_path, "created")

    def on_modified(self, event):
        if event.is_directory:
            return
        if self._is_supported(event.src_path):
            self._dispatch_sync(event.src_path, "modified")

    def on_deleted(self, event):
        if event.is_directory:
            return
        if self._is_supported(event.src_path):
            self._dispatch_delete(event.src_path)

    def _dispatch_sync(self, path: str, event_type: str):
        if sync_watched_file_task:
            sync_watched_file_task.delay(path, event_type)

    def _dispatch_delete(self, path: str):
        if delete_watched_file_task:
            delete_watched_file_task.delay(path)
