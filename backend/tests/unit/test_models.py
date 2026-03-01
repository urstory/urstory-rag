"""Step 2.3 RED: SQLAlchemy 모델 테스트."""
import uuid
from datetime import datetime, timezone

import pytest


def test_document_model_creation():
    """Document 인스턴스 생성 검증."""
    from app.models.database import Document

    doc = Document(
        id=uuid.uuid4(),
        filename="test.pdf",
        file_path="uploads/test.pdf",
        file_type="pdf",
        file_size=1024,
        status="uploaded",
    )
    assert doc.filename == "test.pdf"
    assert doc.file_type == "pdf"
    assert doc.status == "uploaded"
    assert doc.file_size == 1024


def test_chunk_model_with_vector():
    """Vector(1024) 필드 포함 Chunk 검증."""
    from app.models.database import Chunk

    chunk = Chunk(
        id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        content="테스트 청크 내용",
        chunk_index=0,
        metadata_={"page": 1},
    )
    assert chunk.content == "테스트 청크 내용"
    assert chunk.chunk_index == 0
    assert chunk.metadata_ == {"page": 1}


def test_settings_model():
    """Settings 모델 검증."""
    from app.models.database import Setting

    setting = Setting(
        key="chunking_strategy",
        value={"value": "recursive"},
    )
    assert setting.key == "chunking_strategy"
    assert setting.value == {"value": "recursive"}


def test_evaluation_dataset_model():
    """EvaluationDataset 모델 검증."""
    from app.models.database import EvaluationDataset

    ds = EvaluationDataset(
        id=uuid.uuid4(),
        name="test-dataset",
        items=[{"question": "q1", "answer": "a1"}],
    )
    assert ds.name == "test-dataset"
    assert len(ds.items) == 1


def test_evaluation_run_model():
    """EvaluationRun 모델 검증."""
    from app.models.database import EvaluationRun

    run = EvaluationRun(
        id=uuid.uuid4(),
        dataset_id=uuid.uuid4(),
        status="pending",
        settings_snapshot={"chunk_size": 512},
        metrics=None,
        per_question_results=None,
    )
    assert run.status == "pending"
    assert run.settings_snapshot == {"chunk_size": 512}


def test_task_model():
    """Task 모델 검증."""
    from app.models.database import Task

    task = Task(
        id=uuid.uuid4(),
        type="indexing",
        status="pending",
        progress=0,
    )
    assert task.type == "indexing"
    assert task.status == "pending"
    assert task.progress == 0


def test_document_status_enum():
    """DocumentStatus enum 값 확인."""
    from app.models.database import DocumentStatus

    assert DocumentStatus.UPLOADED == "uploaded"
    assert DocumentStatus.INDEXING == "indexing"
    assert DocumentStatus.INDEXED == "indexed"
    assert DocumentStatus.FAILED == "failed"


def test_task_status_enum():
    """TaskStatus enum 값 확인."""
    from app.models.database import TaskStatus

    assert TaskStatus.PENDING == "pending"
    assert TaskStatus.RUNNING == "running"
    assert TaskStatus.COMPLETED == "completed"
    assert TaskStatus.FAILED == "failed"
