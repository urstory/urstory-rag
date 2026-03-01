"""Step 4.10: 검색 API 엔드포인트.

POST /api/search       → 검색 + 답변 생성
POST /api/search/debug → 검색 + 파이프라인 트레이스 포함
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.config import RAGSettings
from app.models.schemas import (
    DebugSearchResponse,
    SearchRequest,
    SearchResponse,
    SearchResult,
)
from app.services.search.hybrid import HybridSearchOrchestrator
from app.services.settings import SettingsService

router = APIRouter()

# 글로벌 인스턴스 (lifespan에서 초기화)
_orchestrator: HybridSearchOrchestrator | None = None
_settings_service: SettingsService | None = None


def set_orchestrator(orchestrator: HybridSearchOrchestrator) -> None:
    global _orchestrator
    _orchestrator = orchestrator


def get_orchestrator() -> HybridSearchOrchestrator:
    if _orchestrator is None:
        raise RuntimeError("Search orchestrator not initialized")
    return _orchestrator


def set_search_settings_service(service: SettingsService) -> None:
    global _settings_service
    _settings_service = service


def get_search_settings_service() -> SettingsService:
    if _settings_service is None:
        raise RuntimeError("Settings service not initialized")
    return _settings_service


async def _apply_overrides(
    base: RAGSettings,
    request: SearchRequest,
) -> RAGSettings:
    """요청의 오버라이드를 설정에 적용."""
    overrides = {}
    if request.search_mode is not None:
        overrides["search_mode"] = request.search_mode
    if request.hyde_enabled is not None:
        overrides["hyde_enabled"] = request.hyde_enabled
    if request.reranking_enabled is not None:
        overrides["reranking_enabled"] = request.reranking_enabled
    if request.top_k is not None:
        overrides["reranker_top_k"] = request.top_k

    if overrides:
        return base.model_copy(update=overrides)
    return base


@router.post("/search", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    orchestrator: HybridSearchOrchestrator = Depends(get_orchestrator),
    settings_service: SettingsService = Depends(get_search_settings_service),
):
    """검색 + 답변 생성 API."""
    base_settings = await settings_service.get_settings()
    settings = await _apply_overrides(base_settings, request)

    result = await orchestrator.search(
        request.query, settings, generate_answer=request.generate_answer,
    )

    return SearchResponse(
        query=request.query,
        answer=result.answer or "",
        results=result.documents,
    )


@router.post("/search/debug", response_model=DebugSearchResponse)
async def search_debug(
    request: SearchRequest,
    orchestrator: HybridSearchOrchestrator = Depends(get_orchestrator),
    settings_service: SettingsService = Depends(get_search_settings_service),
):
    """검색 + 파이프라인 트레이스 포함 디버그 API."""
    base_settings = await settings_service.get_settings()
    settings = await _apply_overrides(base_settings, request)

    result = await orchestrator.search(
        request.query, settings, generate_answer=request.generate_answer,
    )

    return DebugSearchResponse(
        query=request.query,
        answer=result.answer or "",
        results=result.documents,
        pipeline_trace=result.trace,
    )
