"""Step 6.5 RED: RAGAS 평가 엔진 단위 테스트."""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.database import Base, EvaluationDataset, EvaluationRun

TEST_DATABASE_URL = "postgresql+asyncpg://admin:changeme_strong_password@localhost:5432/shared_test"


@pytest_asyncio.fixture
async def ragas_db():
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
async def sample_dataset_and_run(ragas_db):
    """샘플 데이터셋과 pending 상태의 run을 DB에 삽입."""
    ds = EvaluationDataset(
        name="테스트 QA",
        items=[
            {
                "question": "연차 절차는?",
                "ground_truth": "사내 포털에서 신청",
                "source_documents": [],
                "category": "인사",
            },
        ],
    )
    ragas_db.add(ds)
    await ragas_db.commit()
    await ragas_db.refresh(ds)

    run = EvaluationRun(dataset_id=ds.id, status="pending")
    ragas_db.add(run)
    await ragas_db.commit()
    await ragas_db.refresh(run)

    return ds, run


def _make_mock_patches(ragas_db):
    """공통 mock 패치 목록을 반환한다."""

    @asynccontextmanager
    async def fake_session():
        yield ragas_db

    return {
        "evaluate": patch("app.services.evaluation.ragas.evaluate"),
        "session": patch(
            "app.services.evaluation.ragas.RAGASEvaluator._get_db_session",
            return_value=fake_session(),
        ),
        "search": patch(
            "app.services.evaluation.ragas.RAGASEvaluator._run_search",
            new_callable=AsyncMock,
            return_value={"answer": "답변", "contexts": ["컨텍스트"]},
        ),
        "metrics": patch(
            "app.services.evaluation.ragas.RAGASEvaluator._build_metrics",
            return_value=[],  # mock 메트릭
        ),
    }


def _mock_ragas_result():
    """RAGAS evaluate 반환값 mock."""
    import pandas as pd

    mock_df = pd.DataFrame([{
        "faithfulness": 0.85,
        "answer_relevancy": 0.78,
        "context_precision": 0.90,
        "context_recall": 0.82,
    }])
    mock_result = MagicMock()
    mock_result.to_pandas.return_value = mock_df
    return mock_result


class TestRAGASEvaluator:
    """RAGAS 평가 엔진 테스트 (외부 서비스 mock)."""

    @pytest.mark.asyncio
    async def test_evaluate_updates_run_status(self, ragas_db, sample_dataset_and_run):
        """평가 완료 후 run status가 completed로 변경."""
        ds, run = sample_dataset_and_run
        patches = _make_mock_patches(ragas_db)

        with patches["evaluate"] as mock_eval, patches["session"], patches["search"], patches["metrics"]:
            mock_eval.return_value = _mock_ragas_result()

            from app.services.evaluation.ragas import RAGASEvaluator
            evaluator = RAGASEvaluator()
            await evaluator.evaluate(str(ds.id), str(run.id))

        await ragas_db.refresh(run)
        assert run.status == "completed"

    @pytest.mark.asyncio
    async def test_evaluate_stores_metrics(self, ragas_db, sample_dataset_and_run):
        """평가 결과에 4개 메트릭이 저장."""
        ds, run = sample_dataset_and_run
        patches = _make_mock_patches(ragas_db)

        with patches["evaluate"] as mock_eval, patches["session"], patches["search"], patches["metrics"]:
            mock_eval.return_value = _mock_ragas_result()

            from app.services.evaluation.ragas import RAGASEvaluator
            evaluator = RAGASEvaluator()
            await evaluator.evaluate(str(ds.id), str(run.id))

        await ragas_db.refresh(run)
        assert run.metrics is not None
        assert "faithfulness" in run.metrics
        assert "answer_relevancy" in run.metrics
        assert "context_precision" in run.metrics
        assert "context_recall" in run.metrics

    @pytest.mark.asyncio
    async def test_evaluate_stores_settings_snapshot(self, ragas_db, sample_dataset_and_run):
        """평가 시점의 설정 스냅샷이 저장."""
        ds, run = sample_dataset_and_run
        patches = _make_mock_patches(ragas_db)

        with patches["evaluate"] as mock_eval, patches["session"], patches["search"], patches["metrics"]:
            mock_eval.return_value = _mock_ragas_result()

            from app.services.evaluation.ragas import RAGASEvaluator
            evaluator = RAGASEvaluator()
            await evaluator.evaluate(str(ds.id), str(run.id))

        await ragas_db.refresh(run)
        assert run.settings_snapshot is not None
        assert "search_mode" in run.settings_snapshot

    @pytest.mark.asyncio
    async def test_evaluate_failure_sets_failed(self, ragas_db, sample_dataset_and_run):
        """평가 실패 시 run status가 failed로 변경."""
        ds, run = sample_dataset_and_run
        patches = _make_mock_patches(ragas_db)

        with (
            patch("app.services.evaluation.ragas.evaluate", side_effect=RuntimeError("API error")),
            patches["session"],
            patches["search"],
            patches["metrics"],
        ):
            from app.services.evaluation.ragas import RAGASEvaluator
            evaluator = RAGASEvaluator()
            await evaluator.evaluate(str(ds.id), str(run.id))

        await ragas_db.refresh(run)
        assert run.status == "failed"
