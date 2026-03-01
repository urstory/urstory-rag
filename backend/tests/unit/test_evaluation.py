"""Step 6.4-6.5 RED: 평가 데이터셋 및 실행 테스트."""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.database import Base, get_db


# --- Fixtures (conftest.py의 test_db, client와 동일 패턴) ---

TEST_DATABASE_URL = "postgresql+asyncpg://admin:changeme_strong_password@localhost:5432/shared_test"


@pytest_asyncio.fixture
async def eval_db():
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
async def eval_client(eval_db):
    async def override_get_db():
        yield eval_db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


# --- 데이터셋 관리 테스트 ---


SAMPLE_DATASET = {
    "name": "인사 규정 QA",
    "items": [
        {
            "question": "연차 신청 절차가 어떻게 되나요?",
            "ground_truth": "연차 신청은 사내 포털에서 가능합니다.",
            "source_documents": ["doc_001"],
            "category": "인사",
        },
        {
            "question": "퇴직금 계산 방법은?",
            "ground_truth": "퇴직금은 1년 이상 근무 시 지급됩니다.",
            "source_documents": ["doc_002"],
            "category": "인사",
        },
    ],
}


class TestDatasetCreate:
    """데이터셋 생성 테스트."""

    @pytest.mark.asyncio
    async def test_create_dataset(self, eval_client):
        """데이터셋 생성 후 조회 확인."""
        resp = await eval_client.post("/api/evaluation/datasets", json=SAMPLE_DATASET)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "인사 규정 QA"
        assert len(data["items"]) == 2
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_dataset_validation(self, eval_client):
        """필수 필드 누락 시 422 에러."""
        resp = await eval_client.post("/api/evaluation/datasets", json={"name": "빈 데이터셋"})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_dataset_empty_items(self, eval_client):
        """items가 빈 리스트면 422."""
        resp = await eval_client.post(
            "/api/evaluation/datasets", json={"name": "빈", "items": []},
        )
        assert resp.status_code == 422


class TestDatasetList:
    """데이터셋 목록 테스트."""

    @pytest.mark.asyncio
    async def test_list_datasets(self, eval_client):
        """데이터셋 목록 페이징 확인."""
        # 2개 생성
        await eval_client.post("/api/evaluation/datasets", json=SAMPLE_DATASET)
        await eval_client.post(
            "/api/evaluation/datasets",
            json={"name": "두번째", "items": SAMPLE_DATASET["items"][:1]},
        )

        resp = await eval_client.get("/api/evaluation/datasets")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    @pytest.mark.asyncio
    async def test_list_datasets_empty(self, eval_client):
        resp = await eval_client.get("/api/evaluation/datasets")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0


class TestDatasetDetail:
    """데이터셋 상세 조회 테스트."""

    @pytest.mark.asyncio
    async def test_get_dataset(self, eval_client):
        create_resp = await eval_client.post("/api/evaluation/datasets", json=SAMPLE_DATASET)
        ds_id = create_resp.json()["id"]

        resp = await eval_client.get(f"/api/evaluation/datasets/{ds_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "인사 규정 QA"

    @pytest.mark.asyncio
    async def test_get_dataset_not_found(self, eval_client):
        fake_id = str(uuid.uuid4())
        resp = await eval_client.get(f"/api/evaluation/datasets/{fake_id}")
        assert resp.status_code == 404


# --- 평가 실행 테스트 ---


class TestEvaluationRun:
    """평가 실행 API 테스트."""

    @pytest.mark.asyncio
    async def test_evaluation_run_creates_task(self, eval_client):
        """평가 실행 시 run이 생성되고 status=pending."""
        # 데이터셋 생성
        ds_resp = await eval_client.post("/api/evaluation/datasets", json=SAMPLE_DATASET)
        ds_id = ds_resp.json()["id"]

        # 평가 실행 (Celery 태스크는 mock으로 대체)
        from unittest.mock import patch, MagicMock

        with patch("app.tasks.evaluation.run_evaluation_task", new=MagicMock()) as mock_task:
            mock_task.delay = MagicMock()
            resp = await eval_client.post(
                "/api/evaluation/run", json={"dataset_id": ds_id},
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "pending"
        assert data["dataset_id"] == ds_id

    @pytest.mark.asyncio
    async def test_evaluation_run_not_found_dataset(self, eval_client):
        """존재하지 않는 데이터셋으로 평가 실행 시 404."""
        fake_id = str(uuid.uuid4())
        resp = await eval_client.post(
            "/api/evaluation/run", json={"dataset_id": fake_id},
        )
        assert resp.status_code == 404


class TestEvaluationRunList:
    """평가 실행 목록/상세 테스트."""

    @pytest.mark.asyncio
    async def test_list_runs(self, eval_client):
        resp = await eval_client.get("/api/evaluation/runs")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    @pytest.mark.asyncio
    async def test_get_run(self, eval_client):
        """실행 상세 조회."""
        ds_resp = await eval_client.post("/api/evaluation/datasets", json=SAMPLE_DATASET)
        ds_id = ds_resp.json()["id"]

        from unittest.mock import patch, MagicMock

        with patch("app.tasks.evaluation.run_evaluation_task", new=MagicMock()) as mock_task:
            mock_task.delay = MagicMock()
            run_resp = await eval_client.post(
                "/api/evaluation/run", json={"dataset_id": ds_id},
            )

        run_id = run_resp.json()["id"]
        resp = await eval_client.get(f"/api/evaluation/runs/{run_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == run_id

    @pytest.mark.asyncio
    async def test_get_run_not_found(self, eval_client):
        fake_id = str(uuid.uuid4())
        resp = await eval_client.get(f"/api/evaluation/runs/{fake_id}")
        assert resp.status_code == 404


class TestEvaluationCompare:
    """평가 비교 테스트."""

    @pytest.mark.asyncio
    async def test_compare_runs(self, eval_client, eval_db):
        """두 실행 결과 비교."""
        from app.models.database import EvaluationDataset, EvaluationRun

        # DB에 직접 데이터 삽입 (메트릭 포함)
        ds = EvaluationDataset(name="test", items=[{"question": "q", "ground_truth": "a"}])
        eval_db.add(ds)
        await eval_db.commit()
        await eval_db.refresh(ds)

        run1 = EvaluationRun(
            dataset_id=ds.id, status="completed",
            metrics={"faithfulness": 0.8, "answer_relevancy": 0.7},
        )
        run2 = EvaluationRun(
            dataset_id=ds.id, status="completed",
            metrics={"faithfulness": 0.9, "answer_relevancy": 0.75},
        )
        eval_db.add_all([run1, run2])
        await eval_db.commit()
        await eval_db.refresh(run1)
        await eval_db.refresh(run2)

        resp = await eval_client.get(
            f"/api/evaluation/runs/{run1.id}/compare/{run2.id}"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["diff"]["faithfulness"] == pytest.approx(0.1, abs=0.001)
        assert data["diff"]["answer_relevancy"] == pytest.approx(0.05, abs=0.001)
