"""Step 3.5: Celery 비동기 인덱싱 태스크 단위 테스트."""
from unittest.mock import MagicMock, patch

import pytest

from app.worker import celery_app
from app.tasks.indexing import index_document_task


class TestCelerySetup:
    def test_celery_app_created(self):
        """Celery 앱이 생성되었는지 확인."""
        assert celery_app is not None
        assert celery_app.main == "rag"

    def test_index_task_registered(self):
        """index_document_task가 Celery에 등록되었는지 확인."""
        assert index_document_task.name is not None

    def test_index_task_retry_config(self):
        """재시도 설정 확인."""
        assert index_document_task.max_retries == 3


class TestIndexDocumentTask:
    @patch("app.tasks.indexing.asyncio")
    @patch("app.tasks.indexing.get_document_file_path")
    @patch("app.tasks.indexing.create_processor")
    def test_index_task_calls_processor(self, mock_create, mock_get_path, mock_asyncio):
        """태스크가 processor.process를 호출하는지 확인."""
        mock_processor = MagicMock()

        # asyncio.run은 순서대로: get_file_path, create_processor, process
        mock_asyncio.run.side_effect = [
            "/uploads/test.txt",  # get_document_file_path
            mock_processor,       # create_processor
            None,                 # processor.process
        ]

        index_document_task("doc-123")

        assert mock_asyncio.run.call_count == 3
