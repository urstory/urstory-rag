"""평가 API 라우터."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import require_admin
from app.models.database import EvaluationDataset, EvaluationRun, User, get_db

router = APIRouter(tags=["evaluation"])


# --- Schemas ---


class DatasetItemSchema(BaseModel):
    question: str
    ground_truth: str
    source_documents: list[str] = []
    category: str | None = None


class DatasetCreateRequest(BaseModel):
    name: str
    items: list[DatasetItemSchema]

    @field_validator("items")
    @classmethod
    def items_not_empty(cls, v: list) -> list:
        if not v:
            raise ValueError("items must contain at least one item")
        return v


class DatasetResponse(BaseModel):
    id: uuid.UUID
    name: str
    items: list[dict[str, Any]]
    created_at: str | None = None


class DatasetListResponse(BaseModel):
    items: list[DatasetResponse]
    total: int


class EvaluationRunRequest(BaseModel):
    dataset_id: uuid.UUID


class EvaluationRunResponse(BaseModel):
    id: uuid.UUID
    dataset_id: uuid.UUID
    status: str
    settings_snapshot: dict | None = None
    metrics: dict | None = None
    per_question_results: list | None = None
    created_at: str | None = None


class EvaluationRunListResponse(BaseModel):
    items: list[EvaluationRunResponse]
    total: int


class EvaluationCompareResponse(BaseModel):
    run1: EvaluationRunResponse
    run2: EvaluationRunResponse
    diff: dict


# --- Datasets CRUD ---


@router.post("/evaluation/datasets", status_code=201, response_model=DatasetResponse)
async def create_dataset(
    body: DatasetCreateRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    ds = EvaluationDataset(
        name=body.name,
        items=[item.model_dump() for item in body.items],
    )
    db.add(ds)
    await db.commit()
    await db.refresh(ds)
    return DatasetResponse(
        id=ds.id,
        name=ds.name,
        items=ds.items,
        created_at=ds.created_at.isoformat() if ds.created_at else None,
    )


@router.get("/evaluation/datasets", response_model=DatasetListResponse)
async def list_datasets(db: AsyncSession = Depends(get_db), _admin: User = Depends(require_admin)):
    count_result = await db.execute(select(func.count(EvaluationDataset.id)))
    total = count_result.scalar() or 0

    result = await db.execute(
        select(EvaluationDataset).order_by(EvaluationDataset.created_at.desc())
    )
    datasets = result.scalars().all()

    return DatasetListResponse(
        items=[
            DatasetResponse(
                id=ds.id,
                name=ds.name,
                items=ds.items,
                created_at=ds.created_at.isoformat() if ds.created_at else None,
            )
            for ds in datasets
        ],
        total=total,
    )


@router.get("/evaluation/datasets/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(dataset_id: uuid.UUID, db: AsyncSession = Depends(get_db), _admin: User = Depends(require_admin)):
    result = await db.execute(
        select(EvaluationDataset).where(EvaluationDataset.id == dataset_id)
    )
    ds = result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return DatasetResponse(
        id=ds.id,
        name=ds.name,
        items=ds.items,
        created_at=ds.created_at.isoformat() if ds.created_at else None,
    )


# --- Evaluation Runs ---


@router.post("/evaluation/run", status_code=201, response_model=EvaluationRunResponse)
async def start_evaluation_run(
    body: EvaluationRunRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    # 데이터셋 존재 확인
    ds_result = await db.execute(
        select(EvaluationDataset).where(EvaluationDataset.id == body.dataset_id)
    )
    ds = ds_result.scalar_one_or_none()
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found")

    run = EvaluationRun(
        dataset_id=body.dataset_id,
        status="pending",
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    # Celery 태스크 비동기 실행
    try:
        from app.tasks.evaluation import run_evaluation_task
        run_evaluation_task.delay(str(run.dataset_id), str(run.id))
    except Exception:
        pass  # Celery 미기동 시에도 API 응답은 정상 반환

    return _run_to_response(run)


@router.get("/evaluation/runs", response_model=EvaluationRunListResponse)
async def list_evaluation_runs(db: AsyncSession = Depends(get_db), _admin: User = Depends(require_admin)):
    count_result = await db.execute(select(func.count(EvaluationRun.id)))
    total = count_result.scalar() or 0

    result = await db.execute(
        select(EvaluationRun).order_by(EvaluationRun.created_at.desc())
    )
    runs = result.scalars().all()

    return EvaluationRunListResponse(
        items=[_run_to_response(r) for r in runs],
        total=total,
    )


@router.get("/evaluation/runs/{run_id}", response_model=EvaluationRunResponse)
async def get_evaluation_run(run_id: uuid.UUID, db: AsyncSession = Depends(get_db), _admin: User = Depends(require_admin)):
    result = await db.execute(
        select(EvaluationRun).where(EvaluationRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return _run_to_response(run)


@router.get(
    "/evaluation/runs/{run_id1}/compare/{run_id2}",
    response_model=EvaluationCompareResponse,
)
async def compare_evaluation_runs(
    run_id1: uuid.UUID,
    run_id2: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result1 = await db.execute(
        select(EvaluationRun).where(EvaluationRun.id == run_id1)
    )
    run1 = result1.scalar_one_or_none()
    if not run1:
        raise HTTPException(status_code=404, detail=f"Run {run_id1} not found")

    result2 = await db.execute(
        select(EvaluationRun).where(EvaluationRun.id == run_id2)
    )
    run2 = result2.scalar_one_or_none()
    if not run2:
        raise HTTPException(status_code=404, detail=f"Run {run_id2} not found")

    diff = _compute_diff(run1.metrics, run2.metrics)

    return EvaluationCompareResponse(
        run1=_run_to_response(run1),
        run2=_run_to_response(run2),
        diff=diff,
    )


# --- Helpers ---


def _run_to_response(run: EvaluationRun) -> EvaluationRunResponse:
    return EvaluationRunResponse(
        id=run.id,
        dataset_id=run.dataset_id,
        status=run.status,
        settings_snapshot=run.settings_snapshot,
        metrics=run.metrics,
        per_question_results=run.per_question_results,
        created_at=run.created_at.isoformat() if run.created_at else None,
    )


def _compute_diff(metrics1: dict | None, metrics2: dict | None) -> dict:
    """두 실행의 메트릭 차이를 계산한다."""
    if not metrics1 or not metrics2:
        return {}

    diff = {}
    all_keys = set(metrics1.keys()) | set(metrics2.keys())
    for key in all_keys:
        v1 = metrics1.get(key, 0)
        v2 = metrics2.get(key, 0)
        if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
            diff[key] = round(v2 - v1, 4)
    return diff
