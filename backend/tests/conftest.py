"""공통 테스트 Fixture."""
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.main import app
from app.models.database import Base, get_db

# PostgreSQL 테스트 DB (Vector, JSONB 등 PostgreSQL 전용 타입 검증)
TEST_DATABASE_URL = "postgresql+asyncpg://admin:changeme_strong_password@localhost:5432/shared_test"


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
    """FastAPI TestClient (DB 의존성 오버라이드)."""

    async def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db
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
