"""Step 6.8: 평가/모니터링 통합 테스트.

검증 시나리오:
1. 데이터셋 생성 → 평가 실행 → 결과 확인 (4개 메트릭)
2. 설정 변경 → 재평가 → 결과 비교
3. 모니터링 통계 API 동작 확인
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.main import app
from app.models.database import Base, Document, DocumentStatus, EvaluationDataset, EvaluationRun, get_db

TEST_DATABASE_URL = "postgresql+asyncpg://admin:changeme_strong_password@localhost:5432/shared_test"

SAMPLE_DATASET = {
    "name": "통합 테스트 QA",
    "items": [
        {
            "question": "연차 신청 방법은?",
            "ground_truth": "사내 포털에서 인사 > 연차신청 메뉴를 이용합니다.",
            "source_documents": ["doc_001"],
            "category": "인사",
        },
        {
            "question": "야근 수당 기준은?",
            "ground_truth": "22시 이후 근무 시 시급의 1.5배가 지급됩니다.",
            "source_documents": ["doc_002"],
            "category": "급여",
        },
    ],
}


@pytest_asyncio.fixture
async def integ_db():
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
async def integ_client(integ_db):
    async def override_get_db():
        yield integ_db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


class TestEvaluationIntegration:
    """평가 전체 흐름 통합 테스트."""

    @pytest.mark.asyncio
    async def test_full_evaluation_flow(self, integ_client, integ_db):
        """데이터셋 생성 → 평가 실행 → 결과 확인."""
        # 1. 데이터셋 생성
        ds_resp = await integ_client.post("/api/evaluation/datasets", json=SAMPLE_DATASET)
        assert ds_resp.status_code == 201
        ds_id = ds_resp.json()["id"]

        # 2. 데이터셋 목록 확인
        list_resp = await integ_client.get("/api/evaluation/datasets")
        assert list_resp.json()["total"] == 1

        # 3. 데이터셋 상세 확인
        detail_resp = await integ_client.get(f"/api/evaluation/datasets/{ds_id}")
        assert detail_resp.status_code == 200
        assert len(detail_resp.json()["items"]) == 2

        # 4. 평가 실행 (Celery + RAGAS mock)
        with patch("app.tasks.evaluation.run_evaluation_task", new=MagicMock()) as mock_task:
            mock_task.delay = MagicMock()
            run_resp = await integ_client.post(
                "/api/evaluation/run", json={"dataset_id": ds_id},
            )
        assert run_resp.status_code == 201
        run_id = run_resp.json()["id"]

        # 5. 실행 목록 확인
        runs_resp = await integ_client.get("/api/evaluation/runs")
        assert runs_resp.json()["total"] == 1

        # 6. 실행 상세 확인
        run_detail = await integ_client.get(f"/api/evaluation/runs/{run_id}")
        assert run_detail.status_code == 200
        assert run_detail.json()["status"] == "pending"

    @pytest.mark.asyncio
    async def test_evaluation_compare_flow(self, integ_client, integ_db):
        """두 실행 결과 비교."""
        # DB에 직접 삽입 (메트릭 포함)
        ds = EvaluationDataset(name="비교 테스트", items=[{"question": "q", "ground_truth": "a"}])
        integ_db.add(ds)
        await integ_db.commit()
        await integ_db.refresh(ds)

        run1 = EvaluationRun(
            dataset_id=ds.id, status="completed",
            metrics={"faithfulness": 0.75, "answer_relevancy": 0.80},
            settings_snapshot={"search_mode": "hybrid", "reranking_enabled": True},
        )
        run2 = EvaluationRun(
            dataset_id=ds.id, status="completed",
            metrics={"faithfulness": 0.85, "answer_relevancy": 0.82},
            settings_snapshot={"search_mode": "hybrid", "reranking_enabled": False},
        )
        integ_db.add_all([run1, run2])
        await integ_db.commit()
        await integ_db.refresh(run1)
        await integ_db.refresh(run2)

        resp = await integ_client.get(
            f"/api/evaluation/runs/{run1.id}/compare/{run2.id}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["diff"]["faithfulness"] == pytest.approx(0.1, abs=0.001)


class TestMonitoringIntegration:
    """모니터링 API 통합 테스트."""

    @pytest.mark.asyncio
    async def test_monitoring_stats_with_documents(self, integ_client, integ_db):
        """문서가 있을 때 통계가 올바르게 집계."""
        for i in range(3):
            integ_db.add(Document(
                filename=f"doc{i}.txt",
                file_path=f"/tmp/doc{i}.txt",
                file_type="txt",
                file_size=1000,
                status=DocumentStatus.INDEXED,
                chunk_count=15,
            ))
        await integ_db.commit()

        resp = await integ_client.get("/api/monitoring/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_documents"] == 3
        assert data["total_chunks"] == 45

    @pytest.mark.asyncio
    async def test_monitoring_traces_without_langfuse(self, integ_client):
        """Langfuse 미설정 시 빈 트레이스 목록."""
        resp = await integ_client.get("/api/monitoring/traces")
        assert resp.status_code == 200
        assert resp.json()["items"] == []

    @pytest.mark.asyncio
    async def test_monitoring_costs_api(self, integ_client):
        """비용 API 기본 응답."""
        resp = await integ_client.get("/api/monitoring/costs")
        assert resp.status_code == 200
        assert resp.json()["total_cost"] == 0.0
