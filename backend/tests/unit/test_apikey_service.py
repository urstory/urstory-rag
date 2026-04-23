"""API Key 서비스 async 경로 테스트 — create_api_key / authenticate_api_key.

tests/test_apikey.py는 해시/생성만 다루고 있어, 이 파일은 DB 상호작용과
만료 처리, 비활성 키/유저 처리를 포함한 나머지 분기를 채운다.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.models.database import User
from app.services.apikey import (
    authenticate_api_key,
    create_api_key,
    hash_api_key,
)


async def _seed_user(db, role: str = "admin", is_active: bool = True) -> User:
    user = User(
        username=f"apikey_test_{datetime.now().timestamp()}",
        email="apikey@test.local",
        name="API Key Owner",
        role=role,
        is_active=is_active,
        hashed_password="x",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


class TestCreateApiKey:
    @pytest.mark.asyncio
    async def test_create_returns_plain_key_and_model(self, test_db):
        user = await _seed_user(test_db)
        api_key, plain = await create_api_key(test_db, user.id, "default")
        assert plain.startswith("rag_sk_")
        assert api_key.user_id == user.id
        assert api_key.is_active is True
        assert api_key.key_hash == hash_api_key(plain)
        assert api_key.key_prefix == plain[:12]

    @pytest.mark.asyncio
    async def test_create_with_expiration(self, test_db):
        user = await _seed_user(test_db)
        expires = datetime.now(timezone.utc) + timedelta(days=30)
        api_key, _ = await create_api_key(test_db, user.id, "ttl", expires_at=expires)
        assert api_key.expires_at is not None


class TestAuthenticateApiKey:
    @pytest.mark.asyncio
    async def test_authenticate_valid_key_returns_user(self, test_db):
        user = await _seed_user(test_db)
        _, plain = await create_api_key(test_db, user.id, "live")

        found = await authenticate_api_key(test_db, plain)
        assert found is not None
        assert found.id == user.id

    @pytest.mark.asyncio
    async def test_authenticate_unknown_key_returns_none(self, test_db):
        found = await authenticate_api_key(test_db, "rag_sk_does-not-exist")
        assert found is None

    @pytest.mark.asyncio
    async def test_authenticate_expired_key_returns_none(self, test_db):
        user = await _seed_user(test_db)
        past = datetime.now(timezone.utc) - timedelta(minutes=1)
        _, plain = await create_api_key(test_db, user.id, "expired", expires_at=past)

        found = await authenticate_api_key(test_db, plain)
        assert found is None

    @pytest.mark.asyncio
    async def test_authenticate_inactive_user_returns_none(self, test_db):
        user = await _seed_user(test_db, is_active=False)
        _, plain = await create_api_key(test_db, user.id, "deactivated")

        found = await authenticate_api_key(test_db, plain)
        assert found is None

    @pytest.mark.asyncio
    async def test_authenticate_deactivated_key_returns_none(self, test_db):
        user = await _seed_user(test_db)
        api_key, plain = await create_api_key(test_db, user.id, "off")

        api_key.is_active = False
        await test_db.commit()

        found = await authenticate_api_key(test_db, plain)
        assert found is None

    @pytest.mark.asyncio
    async def test_authenticate_bumps_last_used_at(self, test_db):
        user = await _seed_user(test_db)
        api_key, plain = await create_api_key(test_db, user.id, "live")
        assert api_key.last_used_at is None

        found = await authenticate_api_key(test_db, plain)
        assert found is not None

        await test_db.refresh(api_key)
        assert api_key.last_used_at is not None
