"""Step 3.5: Celery 비동기 인덱싱 태스크 단위 테스트."""
from unittest.mock import MagicMock, patch, AsyncMock

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
    @patch("app.tasks.indexing._run_indexing", new_callable=AsyncMock)
    @patch("app.tasks.indexing.asyncio")
    def test_index_task_calls_run_indexing(self, mock_asyncio, mock_run_indexing):
        """태스크가 _run_indexing을 asyncio.run으로 호출하는지 확인."""
        index_document_task("doc-123")

        mock_asyncio.run.assert_called_once()
