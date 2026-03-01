"""디렉토리 감시 오케스트레이터."""
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver

from app.services.watcher.handler import DocumentFileHandler
from app.services.watcher.scanner import DirectoryScanner


class DirectoryWatcherService:
    """디렉토리 감시 서비스 메인 클래스."""

    def __init__(self):
        self.observer: Observer | None = None
        self.scanner = DirectoryScanner()
        self.directories: list[str] = []

    async def start(self, directories: list[str], use_polling: bool = False, polling_interval: int = 5):
        if not directories:
            raise ValueError("감시할 디렉토리가 설정되지 않았습니다")

        self.directories = directories
        handler = DocumentFileHandler()

        ObserverClass = PollingObserver if use_polling else Observer
        self.observer = ObserverClass(
            timeout=polling_interval if use_polling else 1
        )
        for directory in directories:
            self.observer.schedule(handler, directory, recursive=True)
        self.observer.start()

    async def stop(self):
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None

    def is_running(self) -> bool:
        return self.observer is not None and self.observer.is_alive()

    def get_status(self) -> dict:
        return {
            "running": self.is_running(),
            "directories": self.directories,
        }


# 싱글턴 인스턴스
_watcher_service = DirectoryWatcherService()


def get_watcher_service() -> DirectoryWatcherService:
    return _watcher_service
