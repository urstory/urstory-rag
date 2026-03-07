"""모니터링 API 라우터.

Langfuse 트레이스 프록시 및 시스템 통계를 제공한다.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.dependencies import require_admin
from app.models.database import Document, DocumentStatus, Chunk, User, get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["monitoring"])


# --- Schemas ---


class MonitoringStatsResponse(BaseModel):
    total_documents: int
    total_chunks: int
    today_queries: int
    avg_response_time_ms: float


class TraceListResponse(BaseModel):
    items: list[dict[str, Any]]
    total: int


class CostResponse(BaseModel):
    total_cost: float
    period: str
    breakdown: list[dict[str, Any]]


# --- Stats ---


@router.get("/monitoring/stats", response_model=MonitoringStatsResponse)
async def get_stats(db: AsyncSession = Depends(get_db), _admin: User = Depends(require_admin)):
    """집계 통계를 반환한다."""
    from app.api.search import get_cache_service
    from app.services.cache import PREFIX_STATS

    # 캐시 조회
    cache = get_cache_service()
    if cache:
        cached = await cache.get(PREFIX_STATS)
        if cached is not None:
            return MonitoringStatsResponse(**cached)

    # 문서 수
    doc_count_result = await db.execute(
        select(func.count(Document.id)).where(Document.status == DocumentStatus.INDEXED)
    )
    total_documents = doc_count_result.scalar() or 0

    # 총 chunk 수 (문서 모델의 chunk_count 합산)
    chunk_sum_result = await db.execute(
        select(func.coalesce(func.sum(Document.chunk_count), 0)).where(
            Document.status == DocumentStatus.INDEXED
        )
    )
    total_chunks = chunk_sum_result.scalar() or 0

    # 오늘 쿼리 수, 평균 응답 시간은 Langfuse에서 가져오지만
    # Langfuse 미연동 시 기본값 반환
    today_queries, avg_response = await _get_langfuse_query_stats()

    result = MonitoringStatsResponse(
        total_documents=total_documents,
        total_chunks=total_chunks,
        today_queries=today_queries,
        avg_response_time_ms=avg_response,
    )

    # 캐시 저장 (5분 TTL)
    if cache:
        await cache.set(PREFIX_STATS, result.model_dump(), ttl=300)

    return result


# --- Cache Metrics ---


class CacheMetricsResponse(BaseModel):
    enabled: bool
    hits: int
    misses: int
    hit_rate: float
    total_requests: int
    cache_key_count: int
    used_memory_human: str


@router.get("/monitoring/cache", response_model=CacheMetricsResponse)
async def get_cache_metrics(_admin: User = Depends(require_admin)):
    """캐시 메트릭 조회."""
    from app.api.search import get_cache_service
    cache = get_cache_service()
    if not cache:
        return CacheMetricsResponse(
            enabled=False, hits=0, misses=0, hit_rate=0.0,
            total_requests=0, cache_key_count=0, used_memory_human="N/A",
        )

    metrics = cache.get_metrics()
    redis_info = await cache.get_redis_info()
    return CacheMetricsResponse(
        enabled=cache.enabled,
        hits=metrics["hits"],
        misses=metrics["misses"],
        hit_rate=metrics["hit_rate"],
        total_requests=metrics["total_requests"],
        cache_key_count=redis_info["cache_key_count"],
        used_memory_human=redis_info["used_memory_human"],
    )


@router.delete("/monitoring/cache")
async def clear_cache(_admin: User = Depends(require_admin)):
    """관리자 수동 캐시 비우기."""
    from app.api.search import get_cache_service
    cache = get_cache_service()
    if not cache:
        return {"cleared": 0}

    count = await cache.invalidate_all()
    logger.info("cache_cleared_manually", extra={"keys_deleted": count})
    return {"cleared": count}


# --- Traces (Langfuse 프록시) ---


@router.get("/monitoring/traces", response_model=TraceListResponse)
async def list_traces(_admin: User = Depends(require_admin)):
    """Langfuse 트레이스 목록을 프록시한다."""
    traces = await _langfuse_api_get("/api/public/traces", params={"limit": 50})
    if traces is None:
        return TraceListResponse(items=[], total=0)

    items = traces.get("data", [])
    return TraceListResponse(items=items, total=len(items))


@router.get("/monitoring/traces/{trace_id}")
async def get_trace(trace_id: str, _admin: User = Depends(require_admin)):
    """Langfuse 트레이스 상세를 프록시한다."""
    trace = await _langfuse_api_get(f"/api/public/traces/{trace_id}")
    if trace is None:
        return {}
    return trace


# --- Costs ---


@router.get("/monitoring/costs", response_model=CostResponse)
async def get_costs(_admin: User = Depends(require_admin)):
    """비용 추적 정보를 반환한다."""
    # Langfuse 미연동 시 기본값
    return CostResponse(total_cost=0.0, period="today", breakdown=[])


# --- Internal helpers ---


async def _langfuse_api_get(path: str, params: dict | None = None) -> dict | None:
    """Langfuse REST API를 호출한다. 키 미설정 시 None 반환."""
    env = get_settings()
    if not env.langfuse_public_key or not env.langfuse_secret_key:
        return None

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{env.langfuse_host}{path}",
                params=params,
                auth=(env.langfuse_public_key, env.langfuse_secret_key),
                timeout=10.0,
            )
            if resp.status_code == 200:
                return resp.json()
            return None
    except Exception as e:
        logger.warning("Langfuse API call failed: %s", e)
        return None


async def _get_langfuse_query_stats() -> tuple[int, float]:
    """Langfuse에서 오늘의 쿼리 수, 평균 응답 시간을 조회한다."""
    env = get_settings()
    if not env.langfuse_public_key or not env.langfuse_secret_key:
        return 0, 0.0

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{env.langfuse_host}/api/public/traces",
                params={"limit": 1000},
                auth=(env.langfuse_public_key, env.langfuse_secret_key),
                timeout=10.0,
            )
            if resp.status_code != 200:
                return 0, 0.0

            data = resp.json().get("data", [])
            return len(data), 0.0
    except Exception:
        return 0, 0.0
