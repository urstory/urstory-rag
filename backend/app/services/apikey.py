"""API Key 생성, 해싱, 인증 서비스."""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.database import ApiKey, User


def generate_api_key() -> str:
    """rag_sk_ 접두사 + 랜덤 토큰 생성 (총 ~55자)."""
    raw = secrets.token_urlsafe(36)
    return f"rag_sk_{raw}"


def hash_api_key(key: str) -> str:
    """HMAC-SHA256 해시. jwt_secret_key를 서버 시크릿으로 사용."""
    secret = get_settings().jwt_secret_key.encode()
    return hmac.new(secret, key.encode(), hashlib.sha256).hexdigest()


async def create_api_key(
    db: AsyncSession,
    user_id: int,
    name: str,
    expires_at: datetime | None = None,
) -> tuple[ApiKey, str]:
    """API Key를 생성하고 DB에 저장한다. (모델, 평문키) 튜플 반환."""
    plain_key = generate_api_key()
    key_hash = hash_api_key(plain_key)
    key_prefix = plain_key[:12]  # "rag_sk_a3Bf" 식별용

    api_key = ApiKey(
        user_id=user_id,
        key_prefix=key_prefix,
        key_hash=key_hash,
        name=name,
        is_active=True,
        expires_at=expires_at,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    return api_key, plain_key


async def authenticate_api_key(db: AsyncSession, key: str) -> User | None:
    """API Key로 유저를 조회한다. 성공 시 User 반환, 실패 시 None."""
    key_hash = hash_api_key(key)

    result = await db.execute(
        select(ApiKey).where(
            ApiKey.key_hash == key_hash,
            ApiKey.is_active.is_(True),
        )
    )
    api_key = result.scalar_one_or_none()
    if api_key is None:
        return None

    # 만료 체크
    if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
        return None

    # last_used_at 갱신 (매 요청마다 DB write — 향후 Redis 버퍼링으로 최적화 가능)
    api_key.last_used_at = datetime.now(timezone.utc)
    await db.commit()

    # user 로드
    user_result = await db.execute(select(User).where(User.id == api_key.user_id))
    user = user_result.scalar_one_or_none()

    if user is None or not user.is_active:
        return None

    return user
