"""시스템 API: 재인덱싱, 작업상태, 연결 상태."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Task, TaskStatus, get_db
from app.services.document.reindexer import ReindexService

router = APIRouter(tags=["system"])


@router.post("/system/reindex-all")
async def reindex_all(db: AsyncSession = Depends(get_db)):
    """비동기 전체 재인덱싱 시작."""
    service = ReindexService()
    task_id = await service.start_reindex()

    task = Task(
        id=uuid.UUID(task_id),
        type="reindex_all",
        status=TaskStatus.PENDING,
    )
    db.add(task)
    await db.commit()

    return {"task_id": task_id, "status": "pending"}


@router.get("/system/tasks/{task_id}")
async def get_task_status(task_id: str, db: AsyncSession = Depends(get_db)):
    """작업 상태 확인."""
    task = await db.get(Task, uuid.UUID(task_id))
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return {
        "task_id": str(task.id),
        "type": task.type,
        "status": task.status if isinstance(task.status, str) else task.status.value,
        "progress": task.progress,
        "result": task.result,
        "error": task.error,
    }


@router.get("/system/status")
async def system_status():
    """DB, ES, Ollama, Redis 연결 상태."""
    from app.api.health import check_db, check_elasticsearch, check_ollama, check_redis

    components = {
        "database": await check_db(),
        "elasticsearch": await check_elasticsearch(),
        "ollama": await check_ollama(),
        "redis": await check_redis(),
    }

    all_ok = all(v == "connected" for v in components.values())
    return {
        "status": "ok" if all_ok else "degraded",
        "components": components,
    }
