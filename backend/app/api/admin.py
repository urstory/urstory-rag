"""관리자 전용 API 엔드포인트."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import require_admin
from app.models.database import User, get_db
from app.services.auth import hash_password, validate_password_strength

router = APIRouter(prefix="/admin", tags=["admin"])


# --- Schemas ---


class AdminCreateUserRequest(BaseModel):
    username: str
    name: str
    email: str | None = None
    password: str
    role: str = "user"


class AdminUpdateUserRequest(BaseModel):
    name: str | None = None
    email: str | None = None
    role: str | None = None
    is_active: bool | None = None


class AdminUserResponse(BaseModel):
    id: int
    username: str
    email: str | None
    name: str
    role: str
    is_active: bool
    created_at: str | None = None


# --- Endpoints ---


@router.get("/users")
async def list_users(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """사용자 목록."""
    count_result = await db.execute(select(func.count(User.id)))
    total = count_result.scalar() or 0

    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()

    return {
        "items": [_user_to_dict(u) for u in users],
        "total": total,
    }


@router.post("/users", status_code=201, response_model=AdminUserResponse)
async def create_user(
    body: AdminCreateUserRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """관리자가 직접 사용자 생성."""
    result = await db.execute(select(User).where(User.username == body.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="이미 등록된 아이디입니다.")

    try:
        validate_password_strength(body.password)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if body.role not in ("admin", "user"):
        raise HTTPException(status_code=400, detail="역할은 admin 또는 user여야 합니다.")

    user = User(
        username=body.username,
        email=body.email,
        hashed_password=hash_password(body.password),
        name=body.name,
        role=body.role,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return _user_to_response(user)


@router.put("/users/{user_id}", response_model=AdminUserResponse)
async def update_user(
    user_id: int,
    body: AdminUpdateUserRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    """사용자 역할/활성 상태 변경."""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    if body.name is not None:
        user.name = body.name
    if body.email is not None:
        user.email = body.email if body.email else None
    if body.role is not None:
        if body.role not in ("admin", "user"):
            raise HTTPException(status_code=400, detail="역할은 admin 또는 user여야 합니다.")
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active

    await db.commit()
    await db.refresh(user)

    return _user_to_response(user)


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """사용자 삭제."""
    if admin.id == user_id:
        raise HTTPException(status_code=400, detail="자기 자신은 삭제할 수 없습니다.")

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")

    await db.delete(user)
    await db.commit()

    return {"message": "삭제되었습니다.", "id": user_id}


def _user_to_dict(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "name": user.name,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def _user_to_response(user: User) -> AdminUserResponse:
    return AdminUserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        name=user.name,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at.isoformat() if user.created_at else None,
    )
