"""API Key 관리 엔드포인트 (관리자 전용)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.dependencies import require_admin
from app.models.database import ApiKey, User, get_db
from app.models.schemas import ApiKeyCreateRequest, ApiKeyCreateResponse, ApiKeyResponse
from app.services.apikey import create_api_key

router = APIRouter(prefix="/admin", tags=["admin"])

MAX_KEYS_PER_USER = 10


@router.post(
    "/api-keys",
    status_code=201,
    response_model=ApiKeyCreateResponse,
    summary="API Key 발급",
    description="API Key를 발급합니다. **key 필드는 이 응답에서 1회만 반환**되며 다시 조회할 수 없습니다.",
)
async def create_key(
    body: ApiKeyCreateRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    # 활성 키 개수 제한
    count_result = await db.execute(
        select(func.count(ApiKey.id)).where(
            ApiKey.user_id == admin.id,
            ApiKey.is_active.is_(True),
        )
    )
    active_count = count_result.scalar() or 0
    if active_count >= MAX_KEYS_PER_USER:
        raise HTTPException(status_code=400, detail=f"활성 API Key는 최대 {MAX_KEYS_PER_USER}개까지 가능합니다.")

    expires_at = None
    if body.expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=body.expires_in_days)

    api_key, plain_key = await create_api_key(db, admin.id, body.name, expires_at)

    return ApiKeyCreateResponse(
        id=api_key.id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        key=plain_key,
        is_active=api_key.is_active,
        expires_at=api_key.expires_at,
        last_used_at=api_key.last_used_at,
        created_at=api_key.created_at,
    )


@router.get(
    "/api-keys",
    response_model=list[ApiKeyResponse],
    summary="API Key 목록",
    description="발급된 API Key 목록을 조회합니다. 평문 키는 포함되지 않습니다.",
)
async def list_keys(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(
        select(ApiKey).order_by(ApiKey.created_at.desc())
    )
    keys = result.scalars().all()
    return [
        ApiKeyResponse(
            id=k.id,
            name=k.name,
            key_prefix=k.key_prefix,
            is_active=k.is_active,
            expires_at=k.expires_at,
            last_used_at=k.last_used_at,
            created_at=k.created_at,
        )
        for k in keys
    ]


@router.delete(
    "/api-keys/{key_id}",
    summary="API Key 폐기",
    description="API Key를 비활성화합니다. 즉시 인증이 거부됩니다.",
    responses={404: {"description": "키를 찾을 수 없음"}},
)
async def revoke_key(
    key_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    import uuid as _uuid
    api_key = await db.get(ApiKey, _uuid.UUID(key_id))
    if not api_key:
        raise HTTPException(status_code=404, detail="API Key를 찾을 수 없습니다.")

    api_key.is_active = False
    await db.commit()

    return {"message": "API Key가 폐기되었습니다.", "id": key_id}
