"""Step 3.1: 파일 변환 서비스 단위 테스트 (RED → GREEN)."""
import os
from pathlib import Path

import pytest

from app.services.document.converter import DocumentConverter, ConversionResult

FIXTURES = Path(__file__).parent.parent / "fixtures"


class TestDocumentConverter:
    def setup_method(self):
        self.converter = DocumentConverter()

    @pytest.mark.asyncio
    async def test_convert_txt(self):
        """TXT 파일 변환 후 content 추출 확인."""
        result = await self.converter.convert(str(FIXTURES / "sample.txt"))

        assert isinstance(result, ConversionResult)
        assert "한국어 RAG 시스템" in result.content
        assert result.meta["file_type"] == "txt"
        assert result.meta["filename"] == "sample.txt"
        assert result.meta["file_size"] > 0

    @pytest.mark.asyncio
    async def test_convert_markdown(self):
        """Markdown 파일 변환 확인."""
        result = await self.converter.convert(str(FIXTURES / "sample.md"))

        assert "마크다운 파싱" in result.content
        assert result.meta["file_type"] == "md"

    @pytest.mark.asyncio
    async def test_convert_unsupported_type(self):
        """미지원 형식 시 예외 발생 확인."""
        # 임시 .xyz 파일 생성
        unsupported = FIXTURES / "test.xyz"
        unsupported.write_text("unsupported")
        try:
            with pytest.raises(ValueError, match="지원하지 않는 파일"):
                await self.converter.convert(str(unsupported))
        finally:
            unsupported.unlink()

    @pytest.mark.asyncio
    async def test_convert_nonexistent_file(self):
        """존재하지 않는 파일 시 예외 발생."""
        with pytest.raises(FileNotFoundError):
            await self.converter.convert("/nonexistent/file.txt")

    @pytest.mark.asyncio
    async def test_file_type_detection(self):
        """확장자 기반 파일 타입 감지."""
        assert self.converter.detect_file_type("document.pdf") == "pdf"
        assert self.converter.detect_file_type("document.docx") == "docx"
        assert self.converter.detect_file_type("document.txt") == "txt"
        assert self.converter.detect_file_type("document.md") == "md"
