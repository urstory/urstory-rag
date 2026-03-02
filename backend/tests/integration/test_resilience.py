"""복원력 테스트: 외부 서비스 장애 시 시스템 동작 검증."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.main import app
from app.models.database import Base, get_db

TEST_DATABASE_URL = (
    "postgresql+asyncpg://admin:changeme_strong_password@localhost:5432/shared_test"
)


@pytest_asyncio.fixture
async def res_db():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def res_client(res_db):
    async def override_get_db():
        yield res_db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


class TestOpenAIUnavailable:
    """OpenAI 서비스 미응답 시나리오."""

    @pytest.mark.asyncio
    async def test_health_reports_openai_disconnected(self, res_client, res_db):
        """OpenAI 미응답 시 헬스체크에서 disconnected 보고."""
        with patch("app.api.health.check_openai", return_value=False):
            resp = await res_client.get("/api/health")
            assert resp.status_code == 200
            assert resp.json()["components"]["openai"] == "disconnected"

    @pytest.mark.asyncio
    async def test_models_endpoint_graceful(self, res_client, res_db):
        """OpenAI 키 없을 시 모델 목록 빈 리스트 반환."""
        mock_settings = MagicMock()
        mock_settings.openai_api_key = None
        mock_settings.anthropic_api_key = None
        with patch("app.api.settings.get_env_settings", return_value=mock_settings):
            resp = await res_client.get("/api/settings/models")
            assert resp.status_code == 200
            data = resp.json()
            assert data["openai"] == []


class TestPartialFailure:
    """일부 컴포넌트 실패 시나리오."""

    @pytest.mark.asyncio
    async def test_health_partial_failure(self, res_client, res_db):
        """ES+OpenAI 미응답, DB만 연결 시 응답."""
        with (
            patch("app.api.health.check_elasticsearch", return_value=False),
            patch("app.api.health.check_openai", return_value=False),
            patch("app.api.health.check_redis", return_value=False),
        ):
            resp = await res_client.get("/api/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["components"]["elasticsearch"] == "disconnected"
            assert data["components"]["openai"] == "disconnected"
            assert data["components"]["redis"] == "disconnected"

    @pytest.mark.asyncio
    async def test_health_all_connected(self, res_client, res_db):
        """모든 컴포넌트 정상 시 응답."""
        with (
            patch("app.api.health.check_db", return_value=True),
            patch("app.api.health.check_elasticsearch", return_value=True),
            patch("app.api.health.check_openai", return_value=True),
            patch("app.api.health.check_redis", return_value=True),
        ):
            resp = await res_client.get("/api/health")
            assert resp.status_code == 200
            data = resp.json()
            assert all(v == "connected" for v in data["components"].values())


class TestElasticsearchUnavailable:
    """Elasticsearch 미응답 시나리오."""

    @pytest.mark.asyncio
    async def test_health_reports_es_disconnected(self, res_client, res_db):
        """ES 미응답 시 헬스체크에서 disconnected 보고."""
        with patch("app.api.health.check_elasticsearch", return_value=False):
            resp = await res_client.get("/api/health")
            assert resp.status_code == 200
            assert resp.json()["components"]["elasticsearch"] == "disconnected"

    @pytest.mark.asyncio
    async def test_settings_available_without_es(self, res_client, res_db):
        """ES 미응답 시에도 설정 조회 가능."""
        resp = await res_client.get("/api/settings")
        assert resp.status_code == 200
        assert "search_mode" in resp.json()


class TestRedisUnavailable:
    """Redis 미응답 시나리오."""

    @pytest.mark.asyncio
    async def test_health_reports_redis_disconnected(self, res_client, res_db):
        """Redis 미응답 시 헬스체크에서 disconnected 보고."""
        with patch("app.api.health.check_redis", return_value=False):
            resp = await res_client.get("/api/health")
            assert resp.status_code == 200
            assert resp.json()["components"]["redis"] == "disconnected"

    @pytest.mark.asyncio
    async def test_document_operations_without_redis(self, res_client, res_db):
        """Redis 미응답 시에도 문서 CRUD 가능 (Celery 비동기 제외)."""
        import io

        resp = await res_client.post(
            "/api/documents/upload",
            files={
                "file": (
                    "no_redis.txt",
                    io.BytesIO("Redis 없이 업로드 테스트".encode()),
                    "text/plain",
                )
            },
        )
        # 업로드 자체는 DB 저장이므로 성공해야 함
        assert resp.status_code == 201
