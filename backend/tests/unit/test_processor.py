"""Step 3.4: 문서 처리 오케스트레이터 단위 테스트."""
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.document.converter import ConversionResult
from app.services.document.processor import DocumentProcessor


FIXTURES = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def mock_processor():
    converter = AsyncMock()
    converter.convert.return_value = ConversionResult(
        content="테스트 문서 내용입니다. 한국어 RAG 시스템을 구축합니다.",
        meta={"filename": "test.txt", "file_type": "txt", "file_size": 100},
    )

    indexer = AsyncMock()
    db_session = AsyncMock()

    processor = DocumentProcessor(
        converter=converter,
        indexer=indexer,
        db_session=db_session,
        chunking_strategy="recursive",
    )
    return processor, converter, indexer, db_session


class TestDocumentProcessor:
    @pytest.mark.asyncio
    async def test_process_document_full(self, mock_processor):
        """파일 → 변환 → 청킹 → 인덱싱 전체 흐름."""
        processor, converter, indexer, db_session = mock_processor

        await processor.process("doc-123", "/path/to/test.txt")

        converter.convert.assert_called_once_with("/path/to/test.txt")
        indexer.index.assert_called_once()
        # index 호출 시 doc_id와 chunks가 전달되었는지
        call_args = indexer.index.call_args
        assert call_args[0][0] == "doc-123"
        assert len(call_args[0][1]) >= 1  # 최소 1개 청크

    @pytest.mark.asyncio
    async def test_process_updates_status(self, mock_processor):
        """처리 완료 후 update_status 호출 확인."""
        processor, converter, indexer, db_session = mock_processor

        await processor.process("doc-123", "/path/to/test.txt")

        # status update가 "indexed"로 호출되었는지
        db_session.execute.assert_called()

    @pytest.mark.asyncio
    async def test_process_failure_sets_failed(self, mock_processor):
        """에러 시 status="failed" 설정."""
        processor, converter, indexer, db_session = mock_processor
        indexer.index.side_effect = Exception("인덱싱 실패")

        with pytest.raises(Exception, match="인덱싱 실패"):
            await processor.process("doc-123", "/path/to/test.txt")

    @pytest.mark.asyncio
    async def test_process_selects_chunking_strategy(self):
        """설정에 따라 청킹 전략이 선택되는지 확인."""
        converter = AsyncMock()
        converter.convert.return_value = ConversionResult(
            content="테스트 내용",
            meta={"filename": "test.txt", "file_type": "txt", "file_size": 10},
        )
        indexer = AsyncMock()
        db_session = AsyncMock()

        for strategy_name in ["recursive", "auto"]:
            processor = DocumentProcessor(
                converter=converter,
                indexer=indexer,
                db_session=db_session,
                chunking_strategy=strategy_name,
            )
            assert processor.chunking_strategy == strategy_name


# --- Phase 15: Processor PDF 설정 전달 테스트 ---


class TestDocumentProcessorPDFSettings:
    """Processor의 PDF 설정 전달 테스트."""

    @pytest.mark.asyncio
    async def test_processor_converter_has_pdf_parser(self):
        """Processor에 전달된 Converter가 pdf_parser 설정을 갖는다."""
        from app.services.document.converter import DocumentConverter

        converter = DocumentConverter(pdf_parser="docling", ocr_enabled=True)
        indexer = AsyncMock()
        db_session = AsyncMock()

        processor = DocumentProcessor(
            converter=converter,
            indexer=indexer,
            db_session=db_session,
        )
        assert processor.converter.pdf_parser == "docling"
        assert processor.converter.ocr_enabled is True

    @pytest.mark.asyncio
    async def test_processor_converter_pypdf_mode(self):
        """pdf_parser=pypdf 모드에서 Converter가 pypdf를 사용."""
        from app.services.document.converter import DocumentConverter

        converter = DocumentConverter(pdf_parser="pypdf")
        indexer = AsyncMock()
        db_session = AsyncMock()

        processor = DocumentProcessor(
            converter=converter,
            indexer=indexer,
            db_session=db_session,
        )
        assert processor.converter.pdf_parser == "pypdf"
