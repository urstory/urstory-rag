"""Step 3.6: 문서 CRUD API 단위 테스트."""
import io
import uuid

import pytest
import pytest_asyncio

from app.models.database import Document, DocumentStatus


class TestDocumentsAPI:
    @pytest.mark.asyncio
    async def test_upload_document(self, client, test_db):
        """파일 업로드 후 201 + doc_id 반환."""
        file_content = b"Test document content for upload"
        response = await client.post(
            "/api/documents/upload",
            files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
        )
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["status"] in ("uploaded", "indexing")

    @pytest.mark.asyncio
    async def test_list_documents_pagination(self, client, test_db):
        """페이징 파라미터 동작 확인."""
        # 문서 3개 생성
        for i in range(3):
            doc = Document(
                filename=f"doc{i}.txt",
                file_path=f"/uploads/doc{i}.txt",
                file_type="txt",
                file_size=100,
                status=DocumentStatus.INDEXED,
            )
            test_db.add(doc)
        await test_db.commit()

        response = await client.get("/api/documents?page=1&size=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 3
        assert data["page"] == 1
        assert data["size"] == 2
        assert data["pages"] == 2

    @pytest.mark.asyncio
    async def test_get_document_detail(self, client, test_db):
        """문서 상세 조회."""
        doc = Document(
            filename="detail.txt",
            file_path="/uploads/detail.txt",
            file_type="txt",
            file_size=200,
            status=DocumentStatus.INDEXED,
            chunk_count=5,
        )
        test_db.add(doc)
        await test_db.commit()
        await test_db.refresh(doc)

        response = await client.get(f"/api/documents/{doc.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "detail.txt"
        assert data["chunk_count"] == 5

    @pytest.mark.asyncio
    async def test_delete_document(self, client, test_db):
        """삭제 후 404."""
        doc = Document(
            filename="delete_me.txt",
            file_path="/uploads/delete_me.txt",
            file_type="txt",
            file_size=100,
            status=DocumentStatus.UPLOADED,
        )
        test_db.add(doc)
        await test_db.commit()
        await test_db.refresh(doc)

        response = await client.delete(f"/api/documents/{doc.id}")
        assert response.status_code == 200

        response = await client.get(f"/api/documents/{doc.id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_nonexistent_document(self, client, test_db):
        """존재하지 않는 문서 조회 시 404."""
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/api/documents/{fake_id}")
        assert response.status_code == 404
