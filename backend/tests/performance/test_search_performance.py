"""성능 테스트: 검색 응답 시간, 인덱싱 처리량, 동시 요청 처리.

`pytest.mark.performance` 마커 적용 — 기본 테스트 게이트에서 제외.
별도 실행: pytest tests/performance/ -v -m performance
"""
import asyncio
import io
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.main import app
from app.models.database import Base, get_db
from app.dependencies import get_current_user, require_admin

TEST_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://admin:changeme_strong_password@localhost:5432/shared_test",
)


@pytest_asyncio.fixture
async def perf_db():
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
async def perf_client(perf_db):
    async def override_get_db():
        yield perf_db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: type('User', (), {'id': 1, 'email': 'admin@test.com', 'name': 'admin', 'role': 'admin', 'is_active': True})()
    app.dependency_overrides[require_admin] = lambda: type('User', (), {'id': 1, 'email': 'admin@test.com', 'name': 'admin', 'role': 'admin', 'is_active': True})()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.mark.performance
class TestSearchPerformance:
    """검색 성능 테스트."""

    @pytest.mark.asyncio
    async def test_health_response_time(self, perf_client):
        """헬스체크 응답 시간 1초 이내."""
        start = time.monotonic()
        resp = await perf_client.get("/api/health")
        elapsed = time.monotonic() - start
        assert resp.status_code == 200
        assert elapsed < 1.0, f"헬스체크 응답 시간 초과: {elapsed:.2f}s"

    @pytest.mark.asyncio
    async def test_settings_response_time(self, perf_client, perf_db):
        """설정 조회 응답 시간 1초 이내."""
        start = time.monotonic()
        resp = await perf_client.get("/api/settings")
        elapsed = time.monotonic() - start
        assert resp.status_code == 200
        assert elapsed < 1.0, f"설정 조회 응답 시간 초과: {elapsed:.2f}s"

    @pytest.mark.asyncio
    async def test_document_list_response_time(self, perf_client, perf_db):
        """문서 목록 조회 응답 시간 2초 이내."""
        start = time.monotonic()
        resp = await perf_client.get("/api/documents")
        elapsed = time.monotonic() - start
        assert resp.status_code == 200
        assert elapsed < 2.0, f"문서 목록 응답 시간 초과: {elapsed:.2f}s"


@pytest.mark.performance
class TestIndexingThroughput:
    """인덱싱 처리량 테스트."""

    @pytest.mark.asyncio
    async def test_batch_upload(self, perf_client, perf_db):
        """10개 문서 순차 업로드 → 전체 30초 이내."""
        import sys

        # Celery task 모듈을 모킹하여 Redis 연결 차단
        mock_module = MagicMock()
        mock_module.index_document_task = MagicMock()
        mock_module.index_document_task.delay = MagicMock()

        with patch.dict(sys.modules, {"app.tasks.indexing": mock_module}):
            start = time.monotonic()
            doc_ids = []

            for i in range(10):
                resp = await perf_client.post(
                    "/api/documents/upload",
                    files={
                        "file": (
                            f"perf_test_{i}.txt",
                            io.BytesIO((f"perf test doc {i}. " * 50 + "\n" * 10).encode()),
                            "text/plain",
                        )
                    },
                )
                assert resp.status_code == 201
                doc_ids.append(resp.json()["id"])

            elapsed = time.monotonic() - start
            assert elapsed < 30.0, f"10개 문서 업로드 시간 초과: {elapsed:.1f}s"

            # 정리
            for doc_id in doc_ids:
                await perf_client.delete(f"/api/documents/{doc_id}")


@pytest.mark.performance
class TestConcurrentRequests:
    """동시 요청 처리 테스트."""

    @pytest.mark.asyncio
    async def test_concurrent_health_checks(self, perf_client):
        """10개 동시 헬스체크 → 모두 성공."""
        tasks = [perf_client.get("/api/health") for _ in range(10)]
        results = await asyncio.gather(*tasks)
        assert all(r.status_code == 200 for r in results)

    @pytest.mark.asyncio
    async def test_concurrent_settings_reads(self, perf_client, perf_db):
        """10개 동시 설정 조회 → 모두 성공."""
        tasks = [perf_client.get("/api/settings") for _ in range(10)]
        results = await asyncio.gather(*tasks)
        assert all(r.status_code == 200 for r in results)

    @pytest.mark.asyncio
    async def test_concurrent_document_list(self, perf_client, perf_db):
        """10개 동시 문서 목록 조회 → 모두 성공."""
        tasks = [perf_client.get("/api/documents") for _ in range(10)]
        results = await asyncio.gather(*tasks)
        assert all(r.status_code == 200 for r in results)
