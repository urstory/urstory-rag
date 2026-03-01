"""통합 테스트: 디렉토리 감시 파이프라인."""
import tempfile
from pathlib import Path

import pytest

from app.services.watcher.scanner import DirectoryScanner


class TestWatcherPipeline:
    @pytest.mark.asyncio
    async def test_watcher_status_api(self, client, test_db):
        """감시 상태 API 응답 확인."""
        response = await client.get("/api/watcher/status")
        assert response.status_code == 200
        data = response.json()
        assert "running" in data
        assert data["running"] is False

    @pytest.mark.asyncio
    async def test_scanner_full_scan(self):
        """전체 스캔으로 누락 파일 보정 확인."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 지원 파일 생성
            Path(tmpdir, "doc1.txt").write_text("first document")
            Path(tmpdir, "doc2.md").write_text("# Second")
            Path(tmpdir, "image.jpg").write_text("not a document")

            scanner = DirectoryScanner()
            files = scanner.scan_supported_files(tmpdir)

            assert len(files) == 2

    @pytest.mark.asyncio
    async def test_scanner_hash_change_detection(self):
        """해시 변경 감지."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir, "test.txt")
            file_path.write_text("original content")

            scanner = DirectoryScanner()
            hash1 = scanner.compute_hash(str(file_path))

            file_path.write_text("modified content")
            hash2 = scanner.compute_hash(str(file_path))

            assert hash1 != hash2
