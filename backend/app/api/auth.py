"""인증 API 엔드포인트."""
from datetime import datetime, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.middleware.rate_limit import limiter
from app.dependencies import get_current_user
from app.models.database import User, get_db
from app.services.auth import (
    blacklist_token,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    is_token_blacklisted,
    validate_password_strength,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


# --- Schemas ---


class SignupRequest(BaseModel):
    username: str
    name: str
    email: str | None = None
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    username: str
    email: str | None
    name: str
    role: str
    is_active: bool


class ProfileUpdateRequest(BaseModel):
    name: str | None = None
    email: str | None = None

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, v: str | None) -> str | None:
        if v is not None:
            stripped = v.strip()
            if not stripped:
                raise ValueError("이름은 비어있을 수 없습니다.")
            return stripped
        return v


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


# --- Endpoints ---


@router.post("/signup", status_code=201, response_model=UserResponse)
@limiter.limit("3/minute")
async def signup(request: Request, body: SignupRequest, db: AsyncSession = Depends(get_db)):
    """회원가입. ALLOW_PUBLIC_SIGNUP=false이면 403."""
    env = get_settings()
    if not env.allow_public_signup:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="공개 회원가입이 비활성화되어 있습니다. 관리자에게 문의하세요.",
        )

    # 중복 확인
    result = await db.execute(select(User).where(User.username == body.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="이미 등록된 아이디입니다.")

    try:
        validate_password_strength(body.password)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    user = User(
        username=body.username,
        email=body.email,
        hashed_password=hash_password(body.password),
        name=body.name,
        role="user",
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return UserResponse(
        id=user.id, username=user.username, email=user.email, name=user.name,
        role=user.role, is_active=user.is_active,
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login(request: Request, body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    """로그인 → access_token (body) + refresh_token (HttpOnly Cookie)."""
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다.")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="비활성화된 계정입니다.")

    access_token = create_access_token(user.id, user.role)
    refresh_token = create_refresh_token(user.id)

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=False,  # 개발환경: False, 프로덕션: True
        samesite="lax",
        max_age=7 * 24 * 3600,
        path="/api/auth",
    )

    return TokenResponse(access_token=access_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Cookie의 refresh_token으로 새 access_token 발급."""
    if not refresh_token:
        raise HTTPException(status_code=401, detail="리프레시 토큰이 없습니다.")

    try:
        payload = decode_token(refresh_token)
    except Exception:
        raise HTTPException(status_code=401, detail="유효하지 않은 리프레시 토큰입니다.")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰 타입입니다.")

    jti = payload.get("jti")
    if jti and await is_token_blacklisted(jti):
        raise HTTPException(status_code=401, detail="로그아웃된 토큰입니다.")

    user_id = int(payload["sub"])
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="사용자를 찾을 수 없습니다.")

    access_token = create_access_token(user.id, user.role)

    # 새 refresh_token도 발급 (rotation)
    new_refresh = create_refresh_token(user.id)
    response.set_cookie(
        key="refresh_token",
        value=new_refresh,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=7 * 24 * 3600,
        path="/api/auth",
    )

    # 이전 refresh_token 블랙리스트
    if jti:
        exp = payload.get("exp", 0)
        ttl = max(int(exp - datetime.now(timezone.utc).timestamp()), 0)
        if ttl > 0:
            await blacklist_token(jti, ttl)

    return TokenResponse(access_token=access_token)


@router.post("/logout")
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    user: User = Depends(get_current_user),
):
    """로그아웃: Cookie 삭제 + 토큰 블랙리스트."""
    # refresh_token 블랙리스트
    if refresh_token:
        try:
            payload = decode_token(refresh_token)
            jti = payload.get("jti")
            if jti:
                exp = payload.get("exp", 0)
                ttl = max(int(exp - datetime.now(timezone.utc).timestamp()), 0)
                if ttl > 0:
                    await blacklist_token(jti, ttl)
        except Exception:
            pass

    response.delete_cookie("refresh_token", path="/api/auth")
    return {"message": "로그아웃되었습니다."}


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    """현재 사용자 정보."""
    return UserResponse(
        id=user.id, username=user.username, email=user.email, name=user.name,
        role=user.role, is_active=user.is_active,
    )


@router.put("/me", response_model=UserResponse)
async def update_profile(
    body: ProfileUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """프로필(이름, 이메일) 변경."""
    if body.name is not None:
        user.name = body.name
    if body.email is not None:
        user.email = body.email if body.email else None
    await db.commit()
    await db.refresh(user)

    return UserResponse(
        id=user.id, username=user.username, email=user.email, name=user.name,
        role=user.role, is_active=user.is_active,
    )


@router.put("/me/password")
async def change_password(
    body: PasswordChangeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """비밀번호 변경."""
    if not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="현재 비밀번호가 올바르지 않습니다.")

    try:
        validate_password_strength(body.new_password)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    user.hashed_password = hash_password(body.new_password)
    await db.commit()

    return {"message": "비밀번호가 변경되었습니다."}
