"""Phase 15 Step 2: DoclingPDFConverter 단위 테스트."""
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.document.converter import ConversionResult


class TestDoclingPDFConverterInit:
    """DoclingPDFConverter 초기화 테스트."""

    def test_default_settings(self):
        """기본 설정으로 초기화."""
        from app.services.document.docling_converter import DoclingPDFConverter

        conv = DoclingPDFConverter()
        assert conv.ocr_enabled is False
        assert conv.ocr_languages == ["ko", "en"]
        assert conv.table_extraction_enabled is True
        assert conv._converter is None  # 지연 초기화

    def test_custom_settings(self):
        """커스텀 설정으로 초기화."""
        from app.services.document.docling_converter import DoclingPDFConverter

        conv = DoclingPDFConverter(
            ocr_enabled=True,
            ocr_languages=["ko", "en", "ja"],
            table_extraction_enabled=False,
        )
        assert conv.ocr_enabled is True
        assert conv.ocr_languages == ["ko", "en", "ja"]
        assert conv.table_extraction_enabled is False

    def test_lazy_initialization(self):
        """import 시 Docling 모델을 로드하지 않는다."""
        from app.services.document.docling_converter import DoclingPDFConverter

        conv = DoclingPDFConverter()
        # _converter가 None → 모델 미로드
        assert conv._converter is None


class TestDoclingPDFConverterConvert:
    """DoclingPDFConverter.convert() 테스트."""

    @pytest.mark.asyncio
    async def test_convert_returns_markdown(self):
        """PDF 변환 시 마크다운 콘텐츠 반환."""
        from app.services.document.docling_converter import DoclingPDFConverter

        conv = DoclingPDFConverter()

        # Docling의 DocumentConverter를 mock
        mock_doc = MagicMock()
        mock_doc.export_to_markdown.return_value = "# 제목\n\n본문 내용입니다."

        mock_result = MagicMock()
        mock_result.document = mock_doc

        mock_docling_converter = MagicMock()
        mock_docling_converter.convert.return_value = mock_result

        conv._converter = mock_docling_converter

        # 임시 PDF 파일 생성
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF-1.4 dummy")
            tmp_path = f.name

        try:
            result = await conv.convert(tmp_path)
            assert isinstance(result, ConversionResult)
            assert "# 제목" in result.content
            assert "본문 내용" in result.content
            assert result.meta["converter"] == "docling"
            assert result.meta["file_type"] == "pdf"
        finally:
            Path(tmp_path).unlink()

    @pytest.mark.asyncio
    async def test_convert_with_tables(self):
        """테이블 포함 PDF에서 마크다운 테이블 추출."""
        from app.services.document.docling_converter import DoclingPDFConverter

        conv = DoclingPDFConverter(table_extraction_enabled=True)

        mock_doc = MagicMock()
        mock_doc.export_to_markdown.return_value = (
            "# 보고서\n\n| 항목 | 값 |\n|------|----|\n| GDP | 1.5% |\n"
        )
        mock_result = MagicMock()
        mock_result.document = mock_doc
        mock_docling_converter = MagicMock()
        mock_docling_converter.convert.return_value = mock_result
        conv._converter = mock_docling_converter

        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF-1.4 dummy")
            tmp_path = f.name

        try:
            result = await conv.convert(tmp_path)
            assert "|" in result.content  # 마크다운 테이블 마커
            assert "GDP" in result.content
        finally:
            Path(tmp_path).unlink()

    @pytest.mark.asyncio
    async def test_metadata_includes_converter_info(self):
        """메타데이터에 변환 엔진 정보 포함."""
        from app.services.document.docling_converter import DoclingPDFConverter

        conv = DoclingPDFConverter()

        mock_doc = MagicMock()
        mock_doc.export_to_markdown.return_value = "텍스트"
        mock_result = MagicMock()
        mock_result.document = mock_doc
        mock_docling_converter = MagicMock()
        mock_docling_converter.convert.return_value = mock_result
        conv._converter = mock_docling_converter

        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF-1.4 dummy")
            tmp_path = f.name

        try:
            result = await conv.convert(tmp_path)
            assert result.meta["converter"] == "docling"
            assert result.meta["filename"].endswith(".pdf")
            assert result.meta["file_size"] > 0
        finally:
            Path(tmp_path).unlink()

    @pytest.mark.asyncio
    async def test_fallback_to_pypdf_on_docling_failure(self):
        """Docling 실패 시 pypdf 폴백."""
        from app.services.document.docling_converter import DoclingPDFConverter

        conv = DoclingPDFConverter()

        # Docling 변환이 예외를 발생시키도록 설정
        mock_docling_converter = MagicMock()
        mock_docling_converter.convert.side_effect = RuntimeError("모델 로딩 실패")
        conv._converter = mock_docling_converter

        # pypdf 폴백도 mock
        with patch.object(conv, "_fallback_pypdf") as mock_fallback:
            mock_fallback.return_value = ConversionResult(
                content="pypdf로 추출된 텍스트",
                meta={"converter": "pypdf_fallback", "file_type": "pdf"},
            )

            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
                f.write(b"%PDF-1.4 dummy")
                tmp_path = f.name

            try:
                result = await conv.convert(tmp_path)
                assert result.meta["converter"] == "pypdf_fallback"
                mock_fallback.assert_called_once()
            finally:
                Path(tmp_path).unlink()

    @pytest.mark.asyncio
    async def test_convert_docx_via_docling(self):
        """DOCX 변환도 Docling으로 처리."""
        from app.services.document.docling_converter import DoclingPDFConverter

        conv = DoclingPDFConverter()

        mock_doc = MagicMock()
        mock_doc.export_to_markdown.return_value = "# Word 문서\n\n내용입니다."
        mock_result = MagicMock()
        mock_result.document = mock_doc
        mock_docling_converter = MagicMock()
        mock_docling_converter.convert.return_value = mock_result
        conv._converter = mock_docling_converter

        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            f.write(b"PK dummy docx")
            tmp_path = f.name

        try:
            result = await conv.convert(tmp_path)
            assert "Word 문서" in result.content
            assert result.meta["converter"] == "docling"
        finally:
            Path(tmp_path).unlink()


class TestDoclingPDFConverterGetConverter:
    """_get_converter() 지연 초기화 테스트."""

    def test_get_converter_creates_once(self):
        """_get_converter는 한 번만 생성한다."""
        from app.services.document.docling_converter import DoclingPDFConverter

        conv = DoclingPDFConverter()

        with patch("docling.document_converter.DocumentConverter") as MockDC:
            mock_instance = MagicMock()
            MockDC.return_value = mock_instance

            result1 = conv._get_converter()
            result2 = conv._get_converter()

            assert result1 is result2
            MockDC.assert_called_once()  # 한 번만 생성

    def test_get_converter_ocr_settings(self):
        """OCR 활성화 시 EasyOcrOptions가 설정된다."""
        from app.services.document.docling_converter import DoclingPDFConverter

        conv = DoclingPDFConverter(ocr_enabled=True, ocr_languages=["ko", "en"])

        with patch("docling.document_converter.DocumentConverter") as MockDC:
            MockDC.return_value = MagicMock()
            conv._get_converter()

            # DocumentConverter 호출 시 format_options에 OCR 설정이 포함
            call_kwargs = MockDC.call_args[1]
            from docling.datamodel.base_models import InputFormat
            pdf_option = call_kwargs["format_options"][InputFormat.PDF]
            assert pdf_option.pipeline_options.do_ocr is True

    def test_get_converter_table_disabled(self):
        """테이블 추출 비활성 시 do_table_structure=False."""
        from app.services.document.docling_converter import DoclingPDFConverter

        conv = DoclingPDFConverter(table_extraction_enabled=False)

        with patch("docling.document_converter.DocumentConverter") as MockDC:
            MockDC.return_value = MagicMock()
            conv._get_converter()

            call_kwargs = MockDC.call_args[1]
            from docling.datamodel.base_models import InputFormat
            pdf_option = call_kwargs["format_options"][InputFormat.PDF]
            assert pdf_option.pipeline_options.do_table_structure is False
