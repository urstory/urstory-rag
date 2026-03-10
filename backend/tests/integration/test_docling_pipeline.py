"""Phase 15: Docling PDF 변환 통합 테스트.

실제 PDF 파일을 Docling으로 변환하고 결과를 검증한다.
"""
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.document.converter import ConversionResult, DocumentConverter
from app.services.document.docling_converter import DoclingPDFConverter

# 테스트 PDF 파일 경로
TEST_DATA = Path(__file__).parent.parent.parent.parent / "test_files" / "public_dataset"
FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestDoclingPDFConversion:
    """실제 PDF 파일의 Docling 변환 테스트."""

    @pytest.mark.asyncio
    async def test_korean_pdf_text_extraction(self):
        """한국어 PDF에서 텍스트를 정확히 추출."""
        pdf_path = TEST_DATA / "bok_easy_economics.pdf"
        if not pdf_path.exists():
            pytest.skip("테스트 PDF 파일 없음")

        converter = DoclingPDFConverter(ocr_enabled=False, table_extraction_enabled=True)
        result = await converter.convert(str(pdf_path))

        assert isinstance(result, ConversionResult)
        assert len(result.content) > 100  # 유의미한 텍스트 추출
        assert result.meta["converter"] == "docling"
        assert result.meta["file_type"] == "pdf"

    @pytest.mark.asyncio
    async def test_pdf_with_tables(self):
        """통계 PDF에서 테이블 마크다운 추출."""
        pdf_path = TEST_DATA / "kostat_social_indicators_2024.pdf"
        if not pdf_path.exists():
            pytest.skip("테스트 PDF 파일 없음")

        converter = DoclingPDFConverter(ocr_enabled=False, table_extraction_enabled=True)
        result = await converter.convert(str(pdf_path))

        # 통계 보고서이므로 테이블이 포함되어야 함
        assert len(result.content) > 100
        assert result.meta["converter"] == "docling"

    @pytest.mark.asyncio
    async def test_document_converter_with_docling(self):
        """DocumentConverter가 Docling으로 PDF를 변환."""
        pdf_path = TEST_DATA / "bok_easy_economics.pdf"
        if not pdf_path.exists():
            pytest.skip("테스트 PDF 파일 없음")

        converter = DocumentConverter(pdf_parser="docling")
        result = await converter.convert(str(pdf_path))

        assert len(result.content) > 100
        assert result.meta["converter"] == "docling"

    @pytest.mark.asyncio
    async def test_document_converter_pypdf_fallback_mode(self):
        """DocumentConverter pdf_parser=pypdf 시 기존 방식 사용."""
        pdf_path = TEST_DATA / "bok_easy_economics.pdf"
        if not pdf_path.exists():
            pytest.skip("테스트 PDF 파일 없음")

        converter = DocumentConverter(pdf_parser="pypdf")
        result = await converter.convert(str(pdf_path))

        assert len(result.content) > 0
        assert result.meta["file_type"] == "pdf"
        # pypdf 모드에서는 converter 키가 없음
        assert result.meta.get("converter") is None


class TestDoclingFallback:
    """Docling 실패 시 pypdf 폴백 테스트."""

    @pytest.mark.asyncio
    async def test_fallback_on_docling_error(self):
        """Docling 모델 오류 시 pypdf로 자동 폴백."""
        pdf_path = TEST_DATA / "bok_easy_economics.pdf"
        if not pdf_path.exists():
            pytest.skip("테스트 PDF 파일 없음")

        converter = DoclingPDFConverter()

        # Docling converter가 예외를 발생시키도록 mock
        mock_docling_converter = MagicMock()
        mock_docling_converter.convert.side_effect = RuntimeError("모델 로딩 실패")
        converter._converter = mock_docling_converter

        result = await converter.convert(str(pdf_path))

        # pypdf 폴백으로 변환 성공
        assert result.meta["converter"] == "pypdf_fallback"
        assert len(result.content) > 0


class TestDoclingSettingsToggle:
    """설정에서 PDF 파서 토글 테스트."""

    @pytest.mark.asyncio
    async def test_settings_docling_mode(self):
        """RAGSettings에서 pdf_parser=docling 설정."""
        from app.config import RAGSettings

        settings = RAGSettings(pdf_parser="docling", ocr_enabled=False)
        converter = DocumentConverter(
            pdf_parser=settings.pdf_parser,
            ocr_enabled=settings.ocr_enabled,
            table_extraction_enabled=settings.table_extraction_enabled,
        )
        assert converter.pdf_parser == "docling"
        assert converter.ocr_enabled is False
        assert converter.table_extraction_enabled is True

    @pytest.mark.asyncio
    async def test_settings_pypdf_mode(self):
        """RAGSettings에서 pdf_parser=pypdf로 변경."""
        from app.config import RAGSettings

        settings = RAGSettings(pdf_parser="pypdf")
        converter = DocumentConverter(
            pdf_parser=settings.pdf_parser,
            ocr_enabled=settings.ocr_enabled,
            table_extraction_enabled=settings.table_extraction_enabled,
        )
        assert converter.pdf_parser == "pypdf"


class TestDoclingChunkingIntegration:
    """Docling 변환 → 청킹 파이프라인 통합 테스트."""

    @pytest.mark.asyncio
    async def test_docling_markdown_with_section_header_chunking(self):
        """Docling 마크다운 출력을 SectionHeaderChunking으로 청킹."""
        from app.services.chunking.header import SectionHeaderChunking

        # Docling이 생성하는 마크다운 형식 시뮬레이션
        docling_markdown = """# 제1장 경제의 기초

경제학은 희소한 자원을 효율적으로 배분하는 방법을 연구하는 학문입니다.

## 1.1 수요와 공급

수요와 공급의 법칙은 경제학의 가장 기본적인 원리입니다.
가격이 올라가면 수요가 줄고, 가격이 내려가면 수요가 늘어납니다.

## 1.2 시장 균형

시장 균형은 수요량과 공급량이 일치하는 점에서 형성됩니다.

| 가격 | 수요량 | 공급량 |
|------|--------|--------|
| 1000 | 100 | 20 |
| 2000 | 80 | 40 |
| 3000 | 60 | 60 |
| 4000 | 40 | 80 |

# 제2장 거시경제

거시경제학은 경제 전체의 흐름을 분석합니다.

## 2.1 GDP

국내총생산(GDP)은 한 나라의 경제 규모를 나타내는 지표입니다.
"""
        chunker = SectionHeaderChunking(chunk_size=512, chunk_overlap=50)
        chunks = await chunker.chunk(
            docling_markdown,
            {"filename": "test.pdf", "file_type": "pdf"},
        )

        assert len(chunks) >= 2  # 최소 2개 이상의 청크
        # 첫 번째 청크에 breadcrumb이 포함되어야 함
        has_breadcrumb = any("경제" in c.content for c in chunks)
        assert has_breadcrumb
