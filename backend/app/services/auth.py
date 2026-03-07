"""인증 서비스: 비밀번호 해싱, JWT 토큰, 블랙리스트."""
import re
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import get_settings

ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7
ALGORITHM = "HS256"


def _get_secret_key() -> str:
    key = get_settings().jwt_secret_key
    if not key:
        raise RuntimeError("JWT_SECRET_KEY 환경변수가 설정되지 않았습니다.")
    return key


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(user_id: int, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, _get_secret_key(), algorithm=ALGORITHM)


def create_refresh_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, _get_secret_key(), algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, _get_secret_key(), algorithms=[ALGORITHM])


def validate_password_strength(password: str) -> None:
    """비밀번호 복잡성 검증: 최소 12자, 대소문자+숫자+특수문자."""
    if len(password) < 12:
        raise ValueError("비밀번호는 최소 12자 이상이어야 합니다.")
    if not re.search(r"[A-Z]", password):
        raise ValueError("비밀번호에 대문자가 포함되어야 합니다.")
    if not re.search(r"[a-z]", password):
        raise ValueError("비밀번호에 소문자가 포함되어야 합니다.")
    if not re.search(r"\d", password):
        raise ValueError("비밀번호에 숫자가 포함되어야 합니다.")
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        raise ValueError("비밀번호에 특수문자가 포함되어야 합니다.")


# --- Redis 토큰 블랙리스트 ---

_redis_client = None


async def _get_redis():
    global _redis_client
    if _redis_client is None:
        import redis.asyncio as aioredis
        env = get_settings()
        _redis_client = aioredis.from_url(env.redis_url, decode_responses=True)
    return _redis_client


async def blacklist_token(jti: str, ttl_seconds: int) -> None:
    r = await _get_redis()
    await r.setex(f"token_blacklist:{jti}", ttl_seconds, "1")


async def is_token_blacklisted(jti: str) -> bool:
    r = await _get_redis()
    return await r.exists(f"token_blacklist:{jti}") > 0
