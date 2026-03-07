"""공통 테스트 Fixture."""
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.main import app
from app.models.database import Base, User, get_db
from app.dependencies import get_current_user, require_admin

# PostgreSQL 테스트 DB (Vector, JSONB 등 PostgreSQL 전용 타입 검증)
TEST_DATABASE_URL = "postgresql+asyncpg://admin:changeme_strong_password@localhost:5432/shared_test"


@pytest.fixture(autouse=True)
def _auth_env(monkeypatch):
    """모든 테스트에서 인증 관련 환경변수 설정."""
    monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret-key-for-all-tests-min32chars!!")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    from app.config import get_settings
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class _FakeUser:
    """테스트용 가짜 User 객체 (SQLAlchemy 모델 인스턴스가 아닌 POPO)."""
    def __init__(self, id, username, name, role, email=None, is_active=True):
        self.id = id
        self.username = username
        self.email = email
        self.name = name
        self.role = role
        self.is_active = is_active
        self.hashed_password = ""


_admin_user = _FakeUser(id=1, username="testadmin", name="테스트 관리자", role="admin", email="admin@test.com")
_regular_user = _FakeUser(id=2, username="testuser", name="테스트 사용자", role="user")


@pytest_asyncio.fixture
async def test_db():
    """PostgreSQL 테스트 DB 세션. 테스트 후 롤백."""
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
    """FastAPI TestClient — 인증 바이패스 (admin 권한)."""

    async def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: _admin_user
    app.dependency_overrides[require_admin] = lambda: _admin_user

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
def mock_ollama():
    """Mock Ollama HTTP 클라이언트."""
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = {"models": [{"name": "bge-m3"}, {"name": "qwen2.5:7b"}]}
    return mock


@pytest.fixture
def mock_elasticsearch():
    """Mock Elasticsearch 클라이언트."""
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = {"cluster_name": "test", "status": "green"}
    return mock
