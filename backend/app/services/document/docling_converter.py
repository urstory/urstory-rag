"""Docling 기반 PDF/DOCX 레이아웃 인식 변환기.

Docling을 사용하여 PDF/DOCX 파일을 마크다운으로 변환한다.
테이블, 헤더, 다단 컬럼을 구조적으로 인식하며,
실패 시 pypdf로 자동 폴백한다.
"""
from __future__ import annotations

import logging
from pathlib import Path

from app.services.document.converter import ConversionResult

logger = logging.getLogger(__name__)

# 지연 import를 위한 모듈 레벨 참조
DocumentConverter = None
PdfFormatOption = None
InputFormat = None
PdfPipelineOptions = None
EasyOcrOptions = None


class DoclingPDFConverter:
    """Docling을 사용한 레이아웃 인식 PDF/DOCX 변환.

    Docling 실패 시 pypdf로 자동 폴백.
    """

    def __init__(
        self,
        ocr_enabled: bool = False,
        ocr_languages: list[str] | None = None,
        table_extraction_enabled: bool = True,
    ):
        self.ocr_enabled = ocr_enabled
        self.ocr_languages = ocr_languages or ["ko", "en"]
        self.table_extraction_enabled = table_extraction_enabled
        self._converter = None

    def _get_converter(self):
        """Docling DocumentConverter를 지연 초기화."""
        if self._converter is not None:
            return self._converter

        global DocumentConverter, PdfFormatOption, InputFormat, PdfPipelineOptions, EasyOcrOptions

        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import (
            EasyOcrOptions,
            PdfPipelineOptions,
        )
        from docling.document_converter import (
            DocumentConverter,
            PdfFormatOption,
        )

        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = self.ocr_enabled
        pipeline_options.do_table_structure = self.table_extraction_enabled

        if self.ocr_enabled:
            pipeline_options.ocr_options = EasyOcrOptions(
                lang=self.ocr_languages,
                confidence_threshold=0.5,
            )

        self._converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=pipeline_options,
                ),
            }
        )
        return self._converter

    async def convert(self, file_path: str) -> ConversionResult:
        """PDF/DOCX를 마크다운으로 변환. 실패 시 pypdf 폴백."""
        path = Path(file_path)
        file_type = path.suffix.lower().lstrip(".")
        meta = {
            "filename": path.name,
            "file_type": file_type,
            "file_size": path.stat().st_size,
        }

        try:
            converter = self._get_converter()
            result = converter.convert(str(path))
            content = result.document.export_to_markdown()
            meta["converter"] = "docling"
            return ConversionResult(content=content, meta=meta)
        except Exception as e:
            logger.warning(
                "Docling 변환 실패, pypdf 폴백: %s", str(e)[:200]
            )
            return await self._fallback_pypdf(path, meta)

    async def _fallback_pypdf(
        self, path: Path, meta: dict
    ) -> ConversionResult:
        """pypdf 폴백 변환."""
        from haystack.components.converters import PyPDFToDocument
        from haystack.dataclasses import ByteStream

        converter = PyPDFToDocument()
        source = ByteStream.from_file_path(path)
        source.meta["file_path"] = str(path)
        result = converter.run(sources=[source])
        documents = result.get("documents", [])
        content = "\n".join(doc.content for doc in documents if doc.content)
        meta["converter"] = "pypdf_fallback"
        return ConversionResult(content=content, meta=meta)
