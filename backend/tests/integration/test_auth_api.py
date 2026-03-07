"""인증 API 통합 테스트."""
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from unittest.mock import AsyncMock, patch

from app.main import app
from app.models.database import Base, User, get_db
from app.services.auth import hash_password

TEST_DATABASE_URL = "postgresql+asyncpg://admin:changeme_strong_password@localhost:5432/shared_test"


@pytest.fixture(autouse=True)
def auth_env(monkeypatch):
    """인증 관련 환경변수 설정."""
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-for-integration-testing-min32!")
    monkeypatch.setenv("ALLOW_PUBLIC_SIGNUP", "false")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    # Langfuse 비활성화
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    from app.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def test_db():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def client(test_db):
    async def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_user(test_db):
    """테스트용 관리자 사용자 생성."""
    user = User(
        username="testadmin",
        email="admin@test.com",
        hashed_password=hash_password("AdminPass123!@#"),
        name="테스트 관리자",
        role="admin",
        is_active=True,
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest_asyncio.fixture
async def regular_user(test_db):
    """테스트용 일반 사용자 생성."""
    user = User(
        username="testuser",
        hashed_password=hash_password("UserPass123!@#$"),
        name="테스트 사용자",
        role="user",
        is_active=True,
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


async def _login(client, username, password):
    """로그인 헬퍼."""
    resp = await client.post("/api/auth/login", json={"username": username, "password": password})
    return resp


# --- Mock redis for blacklist ---

@pytest.fixture(autouse=True)
def mock_redis():
    """Redis 블랙리스트 함수를 Mock으로 대체."""
    with patch("app.dependencies.is_token_blacklisted", new_callable=AsyncMock, return_value=False):
        with patch("app.services.auth._get_redis", new_callable=AsyncMock):
            yield


# --- Tests ---


class TestLogin:
    async def test_login_success(self, client, admin_user):
        resp = await _login(client, "testadmin", "AdminPass123!@#")
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        # refresh_token이 Cookie에 설정되어야 함
        assert "refresh_token" in resp.cookies

    async def test_login_wrong_password(self, client, admin_user):
        resp = await _login(client, "testadmin", "WrongPassword1!@#")
        assert resp.status_code == 401

    async def test_login_nonexistent_user(self, client):
        resp = await _login(client, "nobody", "SomePass123!@#$")
        assert resp.status_code == 401

    async def test_login_inactive_user(self, client, test_db):
        user = User(
            username="inactiveuser",
            hashed_password=hash_password("InactivePass123!@#"),
            name="비활성 사용자",
            role="user",
            is_active=False,
        )
        test_db.add(user)
        await test_db.commit()

        resp = await _login(client, "inactiveuser", "InactivePass123!@#")
        assert resp.status_code == 403


class TestSignup:
    async def test_signup_blocked_by_default(self, client):
        """ALLOW_PUBLIC_SIGNUP=false일 때 회원가입 차단."""
        resp = await client.post("/api/auth/signup", json={
            "username": "newuser",
            "name": "새 사용자",
            "password": "NewPassword123!@#",
        })
        assert resp.status_code == 403

    async def test_signup_allowed(self, client, monkeypatch):
        """ALLOW_PUBLIC_SIGNUP=true일 때 회원가입 허용."""
        monkeypatch.setenv("ALLOW_PUBLIC_SIGNUP", "true")
        from app.config import get_settings
        get_settings.cache_clear()

        resp = await client.post("/api/auth/signup", json={
            "username": "newuser",
            "name": "새 사용자",
            "email": "new@test.com",
            "password": "NewPassword123!@#",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["username"] == "newuser"
        assert data["email"] == "new@test.com"
        assert data["role"] == "user"

    async def test_signup_without_email(self, client, monkeypatch):
        """이메일 없이 회원가입 가능."""
        monkeypatch.setenv("ALLOW_PUBLIC_SIGNUP", "true")
        from app.config import get_settings
        get_settings.cache_clear()

        resp = await client.post("/api/auth/signup", json={
            "username": "noemail",
            "name": "이메일 없는 사용자",
            "password": "NewPassword123!@#",
        })
        assert resp.status_code == 201
        assert resp.json()["email"] is None

    async def test_signup_weak_password(self, client, monkeypatch):
        monkeypatch.setenv("ALLOW_PUBLIC_SIGNUP", "true")
        from app.config import get_settings
        get_settings.cache_clear()

        resp = await client.post("/api/auth/signup", json={
            "username": "weakpw",
            "name": "약한 비밀번호",
            "password": "short",
        })
        assert resp.status_code == 422 or resp.status_code == 500

    async def test_signup_duplicate_username(self, client, admin_user, monkeypatch):
        monkeypatch.setenv("ALLOW_PUBLIC_SIGNUP", "true")
        from app.config import get_settings
        get_settings.cache_clear()

        resp = await client.post("/api/auth/signup", json={
            "username": "testadmin",
            "name": "중복",
            "password": "DuplicatePass123!@#",
        })
        assert resp.status_code == 409


class TestAuthMe:
    async def test_get_me(self, client, admin_user):
        login_resp = await _login(client, "testadmin", "AdminPass123!@#")
        token = login_resp.json()["access_token"]

        resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "testadmin"
        assert data["role"] == "admin"

    async def test_get_me_no_token(self, client):
        resp = await client.get("/api/auth/me")
        assert resp.status_code == 401


class TestUpdateProfile:
    async def test_update_name(self, client, admin_user):
        login_resp = await _login(client, "testadmin", "AdminPass123!@#")
        token = login_resp.json()["access_token"]

        resp = await client.put(
            "/api/auth/me",
            json={"name": "변경된 이름"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "변경된 이름"

        # GET /me로도 반영 확인
        me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.json()["name"] == "변경된 이름"

    async def test_update_email(self, client, admin_user):
        login_resp = await _login(client, "testadmin", "AdminPass123!@#")
        token = login_resp.json()["access_token"]

        resp = await client.put(
            "/api/auth/me",
            json={"email": "newemail@test.com"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["email"] == "newemail@test.com"

    async def test_update_name_empty(self, client, admin_user):
        login_resp = await _login(client, "testadmin", "AdminPass123!@#")
        token = login_resp.json()["access_token"]

        resp = await client.put(
            "/api/auth/me",
            json={"name": ""},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 422

    async def test_update_no_auth(self, client):
        resp = await client.put("/api/auth/me", json={"name": "이름"})
        assert resp.status_code == 401


class TestProtectedEndpoints:
    async def test_documents_requires_auth(self, client):
        """인증 없이 관리자 API 접근 시 401."""
        resp = await client.get("/api/documents")
        assert resp.status_code == 401 or resp.status_code == 403

    async def test_documents_requires_admin(self, client, regular_user):
        login_resp = await _login(client, "testuser", "UserPass123!@#$")
        token = login_resp.json()["access_token"]

        resp = await client.get("/api/documents", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    async def test_health_no_auth(self, client):
        resp = await client.get("/api/health")
        assert resp.status_code == 200


class TestSecurityHeaders:
    async def test_security_headers_present(self, client):
        resp = await client.get("/api/health")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"
        assert resp.headers.get("X-XSS-Protection") == "1; mode=block"
        assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
        assert "camera=()" in resp.headers.get("Permissions-Policy", "")


class TestAdminAPI:
    async def test_admin_list_users(self, client, admin_user):
        login_resp = await _login(client, "testadmin", "AdminPass123!@#")
        token = login_resp.json()["access_token"]

        resp = await client.get("/api/admin/users", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    async def test_admin_create_user(self, client, admin_user):
        login_resp = await _login(client, "testadmin", "AdminPass123!@#")
        token = login_resp.json()["access_token"]

        resp = await client.post("/api/admin/users", json={
            "username": "createduser",
            "name": "관리자가 만든 사용자",
            "email": "created@test.com",
            "password": "CreatedPass123!@#",
            "role": "user",
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 201
        assert resp.json()["username"] == "createduser"

    async def test_non_admin_cannot_access(self, client, regular_user):
        login_resp = await _login(client, "testuser", "UserPass123!@#$")
        token = login_resp.json()["access_token"]

        resp = await client.get("/api/admin/users", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    async def test_admin_delete_user(self, client, admin_user, regular_user):
        login_resp = await _login(client, "testadmin", "AdminPass123!@#")
        token = login_resp.json()["access_token"]

        resp = await client.delete(
            f"/api/admin/users/{regular_user.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    async def test_admin_cannot_delete_self(self, client, admin_user):
        login_resp = await _login(client, "testadmin", "AdminPass123!@#")
        token = login_resp.json()["access_token"]

        resp = await client.delete(
            f"/api/admin/users/{admin_user.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400
