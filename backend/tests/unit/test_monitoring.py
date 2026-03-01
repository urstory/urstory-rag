"""Step 6.6 RED: 모니터링 API 단위 테스트."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.database import Base, get_db

TEST_DATABASE_URL = "postgresql+asyncpg://admin:changeme_strong_password@localhost:5432/shared_test"


@pytest_asyncio.fixture
async def mon_db():
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

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
async def mon_client(mon_db):
    async def override_get_db():
        yield mon_db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


class TestMonitoringStats:
    """GET /api/monitoring/stats 테스트."""

    @pytest.mark.asyncio
    async def test_monitoring_stats(self, mon_client, mon_db):
        """통계 API가 올바른 형식을 반환."""
        # 문서 2개 삽입
        from app.models.database import Document, DocumentStatus
        for i in range(2):
            mon_db.add(Document(
                filename=f"test{i}.txt",
                file_path=f"/tmp/test{i}.txt",
                file_type="txt",
                file_size=100,
                status=DocumentStatus.INDEXED,
                chunk_count=10,
            ))
        await mon_db.commit()

        resp = await mon_client.get("/api/monitoring/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_documents"] == 2
        assert data["total_chunks"] == 20
        assert "today_queries" in data
        assert "avg_response_time_ms" in data


class TestMonitoringTraces:
    """GET /api/monitoring/traces 테스트."""

    @pytest.mark.asyncio
    async def test_monitoring_traces_list(self, mon_client):
        """Langfuse 미설정 시에도 빈 목록 반환."""
        resp = await mon_client.get("/api/monitoring/traces")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert isinstance(data["items"], list)

    @pytest.mark.asyncio
    async def test_monitoring_trace_detail_not_found(self, mon_client):
        resp = await mon_client.get("/api/monitoring/traces/nonexistent-id")
        assert resp.status_code == 200  # Langfuse 미연동 시 빈 응답


class TestMonitoringCosts:
    """GET /api/monitoring/costs 테스트."""

    @pytest.mark.asyncio
    async def test_monitoring_costs(self, mon_client):
        """비용 추적 API 반환 형식 확인."""
        resp = await mon_client.get("/api/monitoring/costs")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_cost" in data
        assert "period" in data
