"""Step 3.7: 디렉토리 감시 서비스 단위 테스트."""
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.watcher.handler import DocumentFileHandler
from app.services.watcher.scanner import DirectoryScanner


class TestDocumentFileHandler:
    def setup_method(self):
        self.handler = DocumentFileHandler()

    def test_handler_filters_supported_files(self):
        """지원 확장자만 처리하는지 확인."""
        assert self.handler._is_supported("/path/to/doc.pdf") is True
        assert self.handler._is_supported("/path/to/doc.docx") is True
        assert self.handler._is_supported("/path/to/doc.txt") is True
        assert self.handler._is_supported("/path/to/doc.md") is True
        assert self.handler._is_supported("/path/to/doc.xyz") is False
        assert self.handler._is_supported("/path/to/doc.jpg") is False

    def test_handler_filters_directories(self):
        """디렉토리 이벤트 무시."""
        assert self.handler._is_supported("/path/to/directory/") is False

    @patch("app.services.watcher.handler.sync_watched_file_task")
    def test_on_created_dispatches_supported(self, mock_task):
        """지원 파일 생성 시 태스크 디스패치."""
        event = MagicMock()
        event.is_directory = False
        event.src_path = "/watch/dir/new_doc.pdf"

        self.handler.on_created(event)
        mock_task.delay.assert_called_once()

    @patch("app.services.watcher.handler.sync_watched_file_task")
    def test_on_created_ignores_unsupported(self, mock_task):
        """미지원 파일 생성 시 무시."""
        event = MagicMock()
        event.is_directory = False
        event.src_path = "/watch/dir/image.jpg"

        self.handler.on_created(event)
        mock_task.delay.assert_not_called()


class TestDirectoryScanner:
    @pytest.mark.asyncio
    async def test_scanner_detects_new_files(self):
        """신규 파일 감지 확인."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 테스트 파일 생성
            Path(tmpdir, "test.txt").write_text("content")
            Path(tmpdir, "test.pdf").write_text("content")
            Path(tmpdir, "ignore.jpg").write_text("content")

            scanner = DirectoryScanner()
            files = scanner.scan_supported_files(tmpdir)

            assert len(files) == 2
            filenames = {Path(f).name for f in files}
            assert "test.txt" in filenames
            assert "test.pdf" in filenames
            assert "ignore.jpg" not in filenames

    @pytest.mark.asyncio
    async def test_scanner_recursive(self):
        """하위 디렉토리 재귀 스캔."""
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = Path(tmpdir, "sub")
            subdir.mkdir()
            Path(tmpdir, "root.txt").write_text("content")
            Path(subdir, "nested.md").write_text("content")

            scanner = DirectoryScanner()
            files = scanner.scan_supported_files(tmpdir)

            assert len(files) == 2

    def test_compute_file_hash(self):
        """파일 해시 계산."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"test content")
            f.flush()
            path = f.name

        try:
            scanner = DirectoryScanner()
            hash1 = scanner.compute_hash(path)
            hash2 = scanner.compute_hash(path)
            assert hash1 == hash2
            assert len(hash1) == 64  # SHA-256
        finally:
            os.unlink(path)
