"""Phase 15 Step 3: DocumentConverter Docling 통합 테스트."""
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.document.converter import ConversionResult, DocumentConverter


FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestConverterWithDocling:
    """DocumentConverter의 Docling 통합 테스트."""

    @pytest.mark.asyncio
    async def test_pdf_uses_docling_by_default(self):
        """pdf_parser=docling일 때 Docling 사용."""
        converter = DocumentConverter(pdf_parser="docling")

        mock_docling = AsyncMock()
        mock_docling.convert.return_value = ConversionResult(
            content="# Docling 변환 결과",
            meta={"converter": "docling", "file_type": "pdf", "filename": "test.pdf", "file_size": 100},
        )

        with patch(
            "app.services.document.docling_converter.DoclingPDFConverter",
            return_value=mock_docling,
        ):
            result = await converter.convert(str(FIXTURES / "sample.pdf"))

        assert result.meta["converter"] == "docling"
        assert "# Docling 변환 결과" in result.content

    @pytest.mark.asyncio
    async def test_pdf_uses_pypdf_when_configured(self):
        """pdf_parser=pypdf일 때 기존 pypdf 사용."""
        converter = DocumentConverter(pdf_parser="pypdf")
        result = await converter.convert(str(FIXTURES / "sample.pdf"))
        # pypdf 변환이므로 converter 키가 없거나 pypdf
        assert result.meta.get("converter") is None or result.meta.get("converter") != "docling"
        assert result.meta["file_type"] == "pdf"

    @pytest.mark.asyncio
    async def test_txt_unaffected(self):
        """TXT 변환은 영향 없음."""
        converter = DocumentConverter(pdf_parser="docling")
        result = await converter.convert(str(FIXTURES / "sample.txt"))
        assert result.meta["file_type"] == "txt"
        assert "한국어 RAG 시스템" in result.content

    @pytest.mark.asyncio
    async def test_md_unaffected(self):
        """MD 변환은 영향 없음."""
        converter = DocumentConverter(pdf_parser="docling")
        result = await converter.convert(str(FIXTURES / "sample.md"))
        assert result.meta["file_type"] == "md"

    @pytest.mark.asyncio
    async def test_docx_uses_docling_when_configured(self):
        """pdf_parser=docling일 때 DOCX도 Docling 사용."""
        converter = DocumentConverter(pdf_parser="docling")

        mock_docling = AsyncMock()
        mock_docling.convert.return_value = ConversionResult(
            content="# Word 문서 내용",
            meta={"converter": "docling", "file_type": "docx", "filename": "test.docx", "file_size": 200},
        )

        with patch(
            "app.services.document.docling_converter.DoclingPDFConverter",
            return_value=mock_docling,
        ):
            result = await converter.convert(str(FIXTURES / "sample.docx"))

        assert result.meta["converter"] == "docling"

    @pytest.mark.asyncio
    async def test_docx_uses_python_docx_when_pypdf(self):
        """pdf_parser=pypdf일 때 DOCX는 기존 python-docx 사용."""
        converter = DocumentConverter(pdf_parser="pypdf")
        result = await converter.convert(str(FIXTURES / "sample.docx"))
        assert result.meta["file_type"] == "docx"
        # 기존 python-docx 변환이므로 converter 키 없음
        assert result.meta.get("converter") is None

    @pytest.mark.asyncio
    async def test_docling_settings_passed(self):
        """Docling 설정이 DoclingPDFConverter에 전달."""
        converter = DocumentConverter(
            pdf_parser="docling",
            ocr_enabled=True,
            ocr_languages=["ko"],
            table_extraction_enabled=False,
        )

        with patch("app.services.document.docling_converter.DoclingPDFConverter") as MockDocling:
            mock_instance = AsyncMock()
            mock_instance.convert.return_value = ConversionResult(
                content="텍스트",
                meta={"converter": "docling", "file_type": "pdf", "filename": "test.pdf", "file_size": 100},
            )
            MockDocling.return_value = mock_instance

            await converter.convert(str(FIXTURES / "sample.pdf"))

            MockDocling.assert_called_once_with(
                ocr_enabled=True,
                ocr_languages=["ko"],
                table_extraction_enabled=False,
            )

    @pytest.mark.asyncio
    async def test_default_converter_no_docling_args(self):
        """기본 DocumentConverter()는 pdf_parser=docling, 기본 Docling 설정."""
        converter = DocumentConverter()
        assert converter.pdf_parser == "docling"
