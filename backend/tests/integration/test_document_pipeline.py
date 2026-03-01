"""통합 테스트: 문서 파이프라인 (업로드 → 변환 → 청킹 → 인덱싱)."""
import io
import uuid

import pytest
import pytest_asyncio

from app.models.database import Document, DocumentStatus


class TestDocumentPipeline:
    @pytest.mark.asyncio
    async def test_upload_and_list(self, client, test_db):
        """파일 업로드 후 목록에서 조회 가능."""
        # 업로드
        response = await client.post(
            "/api/documents/upload",
            files={"file": ("pipeline_test.txt", io.BytesIO(b"pipeline content"), "text/plain")},
        )
        assert response.status_code == 201
        doc_id = response.json()["id"]

        # 목록 조회
        response = await client.get("/api/documents")
        assert response.status_code == 200
        items = response.json()["items"]
        assert any(d["id"] == doc_id for d in items)

    @pytest.mark.asyncio
    async def test_upload_detail_delete(self, client, test_db):
        """업로드 → 상세 → 삭제 전체 흐름."""
        # 업로드
        response = await client.post(
            "/api/documents/upload",
            files={"file": ("flow_test.txt", io.BytesIO(b"flow test"), "text/plain")},
        )
        doc_id = response.json()["id"]

        # 상세
        response = await client.get(f"/api/documents/{doc_id}")
        assert response.status_code == 200
        assert response.json()["filename"] == "flow_test.txt"

        # 삭제
        response = await client.delete(f"/api/documents/{doc_id}")
        assert response.status_code == 200

        # 삭제 확인
        response = await client.get(f"/api/documents/{doc_id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_system_reindex_all(self, client, test_db):
        """시스템 전체 재인덱싱 API."""
        response = await client.post("/api/system/reindex-all")
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert data["status"] == "pending"
