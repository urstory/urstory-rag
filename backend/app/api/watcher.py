"""감시 제어 API 엔드포인트."""
from fastapi import APIRouter, HTTPException, Query

from app.services.document.watcher import get_watcher_service

router = APIRouter(tags=["watcher"])


@router.get("/watcher/status")
async def get_watcher_status():
    """감시 상태 조회."""
    service = get_watcher_service()
    return service.get_status()


@router.post("/watcher/start")
async def start_watcher(
    directories: list[str] | None = Query(default=None),
    use_polling: bool = False,
):
    """감시 시작."""
    service = get_watcher_service()
    if service.is_running():
        return {"message": "이미 실행 중입니다", "running": True}

    dirs = directories or []
    if not dirs:
        raise HTTPException(status_code=400, detail="감시할 디렉토리를 지정하세요")

    await service.start(dirs, use_polling=use_polling)
    return {"message": "감시가 시작되었습니다", "running": True, "directories": dirs}


@router.post("/watcher/stop")
async def stop_watcher():
    """감시 중지."""
    service = get_watcher_service()
    await service.stop()
    return {"message": "감시가 중지되었습니다", "running": False}


@router.post("/watcher/scan")
async def trigger_scan():
    """수동 전체 스캔."""
    service = get_watcher_service()
    scanner = service.scanner
    files = []
    for d in service.directories:
        files.extend(scanner.scan_supported_files(d))
    return {"scanned_files": len(files), "directories": service.directories}
