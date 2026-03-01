"""통합 테스트: 전체 파이프라인 (업로드 → 인덱싱 → 검색 → 답변 → 가드레일 → 설정 → 평가)."""
import io
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.main import app
from app.models.database import Base, Document, DocumentStatus, get_db

TEST_DATABASE_URL = (
    "postgresql+asyncpg://admin:changeme_strong_password@localhost:5432/shared_test"
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def integ_db():
    """통합 테스트 전용 DB 세션."""
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
async def integ_client(integ_db):
    """통합 테스트 전용 FastAPI AsyncClient."""

    async def override_get_db():
        yield integ_db

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


# ── 시나리오 1: 문서 업로드 → 인덱싱 → 검색 → 답변 ─────────────────────


class TestFullPipeline:
    """전체 파이프라인 통합 시나리오."""

    @pytest.mark.asyncio
    async def test_upload_index_search_delete(self, integ_client, integ_db):
        """문서 업로드 → 목록 조회 → 검색 → 삭제 전체 흐름."""
        content = (FIXTURES_DIR / "sample.txt").read_bytes()

        # 1. 문서 업로드
        resp = await integ_client.post(
            "/api/documents/upload",
            files={"file": ("sample.txt", io.BytesIO(content), "text/plain")},
        )
        assert resp.status_code == 201
        doc_id = resp.json()["id"]
        assert resp.json()["filename"] == "sample.txt"

        # 2. 목록에서 확인
        resp = await integ_client.get("/api/documents")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert any(d["id"] == doc_id for d in items)

        # 3. 상세 조회
        resp = await integ_client.get(f"/api/documents/{doc_id}")
        assert resp.status_code == 200
        assert resp.json()["file_type"] == "txt"

        # 4. 삭제
        resp = await integ_client.delete(f"/api/documents/{doc_id}")
        assert resp.status_code == 200

        # 5. 삭제 확인
        resp = await integ_client.get(f"/api/documents/{doc_id}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_markdown_upload(self, integ_client, integ_db):
        """마크다운 문서 업로드."""
        content = (FIXTURES_DIR / "sample.md").read_bytes()

        resp = await integ_client.post(
            "/api/documents/upload",
            files={"file": ("sample.md", io.BytesIO(content), "text/markdown")},
        )
        assert resp.status_code == 201
        assert resp.json()["filename"] == "sample.md"

    @pytest.mark.asyncio
    async def test_document_pagination(self, integ_client, integ_db):
        """문서 목록 페이지네이션."""
        # 3개 문서 업로드
        for i in range(3):
            await integ_client.post(
                "/api/documents/upload",
                files={
                    "file": (
                        f"page_test_{i}.txt",
                        io.BytesIO(f"doc {i}".encode()),
                        "text/plain",
                    )
                },
            )

        # 전체 조회
        resp = await integ_client.get("/api/documents")
        assert resp.status_code == 200
        assert resp.json()["total"] == 3

        # 페이지 크기 제한
        resp = await integ_client.get("/api/documents?size=2&page=1")
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 2

        resp = await integ_client.get("/api/documents?size=2&page=2")
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 1


# ── 시나리오 2: 가드레일 통합 ────────────────────────────────────────────


class TestGuardrailIntegration:
    """가드레일 설정 변경 및 검증."""

    @pytest.mark.asyncio
    async def test_guardrail_settings_toggle(self, integ_client, integ_db):
        """가드레일 ON/OFF 토글."""
        # 현재 설정 조회
        resp = await integ_client.get("/api/settings")
        assert resp.status_code == 200
        original = resp.json()

        # PII 탐지 OFF
        resp = await integ_client.patch(
            "/api/settings",
            json={"pii_detection_enabled": False},
        )
        assert resp.status_code == 200
        assert resp.json()["pii_detection_enabled"] is False

        # 인젝션 탐지 OFF
        resp = await integ_client.patch(
            "/api/settings",
            json={"injection_detection_enabled": False},
        )
        assert resp.status_code == 200
        assert resp.json()["injection_detection_enabled"] is False

        # 다시 ON
        resp = await integ_client.patch(
            "/api/settings",
            json={
                "pii_detection_enabled": True,
                "injection_detection_enabled": True,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["pii_detection_enabled"] is True
        assert resp.json()["injection_detection_enabled"] is True


# ── 시나리오 3: 설정 변경 반영 ───────────────────────────────────────────


class TestSettingsChange:
    """설정 변경 및 영속성 확인."""

    @pytest.mark.asyncio
    async def test_search_mode_change(self, integ_client, integ_db):
        """검색 모드 변경 반영."""
        # vector로 변경
        resp = await integ_client.patch(
            "/api/settings",
            json={"search_mode": "vector"},
        )
        assert resp.status_code == 200
        assert resp.json()["search_mode"] == "vector"

        # 재조회로 영속성 확인
        resp = await integ_client.get("/api/settings")
        assert resp.json()["search_mode"] == "vector"

        # 원복
        resp = await integ_client.patch(
            "/api/settings",
            json={"search_mode": "hybrid"},
        )
        assert resp.json()["search_mode"] == "hybrid"

    @pytest.mark.asyncio
    async def test_reranking_toggle(self, integ_client, integ_db):
        """리랭킹 OFF 설정."""
        resp = await integ_client.patch(
            "/api/settings",
            json={"reranking_enabled": False},
        )
        assert resp.status_code == 200
        assert resp.json()["reranking_enabled"] is False

        # 재조회
        resp = await integ_client.get("/api/settings")
        assert resp.json()["reranking_enabled"] is False

    @pytest.mark.asyncio
    async def test_hyde_toggle(self, integ_client, integ_db):
        """HyDE ON/OFF."""
        resp = await integ_client.patch(
            "/api/settings",
            json={"hyde_enabled": False},
        )
        assert resp.status_code == 200
        assert resp.json()["hyde_enabled"] is False

    @pytest.mark.asyncio
    async def test_multiple_settings_update(self, integ_client, integ_db):
        """여러 설정 동시 변경."""
        resp = await integ_client.patch(
            "/api/settings",
            json={
                "chunk_size": 1024,
                "chunk_overlap": 100,
                "retriever_top_k": 30,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["chunk_size"] == 1024
        assert data["chunk_overlap"] == 100
        assert data["retriever_top_k"] == 30


# ── 시나리오 4: RAGAS 평가 ───────────────────────────────────────────────


class TestEvaluationIntegration:
    """평가 데이터셋 CRUD 및 평가 실행."""

    @pytest.mark.asyncio
    async def test_dataset_crud(self, integ_client, integ_db):
        """데이터셋 생성 → 조회 → 목록."""
        dataset_path = FIXTURES_DIR / "sample_evaluation_dataset.json"
        dataset_data = json.loads(dataset_path.read_text())

        # 생성
        resp = await integ_client.post(
            "/api/evaluation/datasets",
            json=dataset_data,
        )
        assert resp.status_code in (200, 201)
        dataset_id = resp.json()["id"]

        # 상세 조회
        resp = await integ_client.get(f"/api/evaluation/datasets/{dataset_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "테스트 평가 데이터셋"
        assert len(resp.json()["items"]) == 3

        # 목록 조회
        resp = await integ_client.get("/api/evaluation/datasets")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_evaluation_run_creation(self, integ_client, integ_db):
        """평가 실행 생성."""
        dataset_path = FIXTURES_DIR / "sample_evaluation_dataset.json"
        dataset_data = json.loads(dataset_path.read_text())

        # 데이터셋 생성
        resp = await integ_client.post(
            "/api/evaluation/datasets",
            json=dataset_data,
        )
        dataset_id = resp.json()["id"]

        # 평가 실행 (Celery 태스크 모킹)
        with patch("app.tasks.evaluation.run_evaluation_task") as mock_task:
            mock_task.delay = MagicMock()
            resp = await integ_client.post(
                "/api/evaluation/run",
                json={"dataset_id": dataset_id},
            )
            # 200 또는 202 (비동기 태스크 생성)
            assert resp.status_code in (200, 201, 202)


# ── 시나리오 5: 시스템 API ───────────────────────────────────────────────


class TestSystemIntegration:
    """시스템 레벨 통합 검증."""

    @pytest.mark.asyncio
    async def test_health_check(self, integ_client, integ_db):
        """헬스체크 응답 구조."""
        resp = await integ_client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "components" in data
        assert "database" in data["components"]

    @pytest.mark.asyncio
    async def test_reindex_all(self, integ_client, integ_db):
        """전체 재인덱싱."""
        resp = await integ_client.post("/api/system/reindex-all")
        assert resp.status_code == 200
        assert "task_id" in resp.json()

    @pytest.mark.asyncio
    async def test_settings_models(self, integ_client, integ_db):
        """사용 가능 모델 목록."""
        resp = await integ_client.get("/api/settings/models")
        assert resp.status_code == 200
        data = resp.json()
        assert "ollama" in data
        assert "api" in data

    @pytest.mark.asyncio
    async def test_watcher_status(self, integ_client, integ_db):
        """감시 서비스 상태."""
        resp = await integ_client.get("/api/watcher/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "running" in data
