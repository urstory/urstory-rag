"""자동 감지 청킹: 파일 타입과 텍스트 구조로 전략 선택."""
import re

from app.services.chunking.base import Chunk, ChunkingStrategy
from app.services.chunking.header import SectionHeaderChunking
from app.services.chunking.recursive import RecursiveChunking
from app.services.generation.base import LLMProvider


class AutoDetectChunking:
    """파일 타입, 평균 문단 길이, 섹션 구조를 분석하여 전략 자동 선택."""

    def __init__(
        self,
        llm_provider: LLMProvider | None = None,
        contextual_enabled: bool = False,
        max_doc_chars: int = 2000,
    ):
        self.llm_provider = llm_provider
        self.contextual_enabled = contextual_enabled
        self.max_doc_chars = max_doc_chars

    def detect_strategy(self, meta: dict | None = None, text: str = "") -> ChunkingStrategy:
        file_type = (meta or {}).get("file_type", "txt")

        # 마크다운/PDF: 섹션 헤더 기반 contextual chunking
        if file_type in ("md", "pdf"):
            return SectionHeaderChunking(chunk_size=1024, chunk_overlap=200)

        # 기본: 단순 재귀 분할
        return RecursiveChunking(chunk_size=1024, chunk_overlap=200)

    async def chunk(self, text: str, meta: dict | None = None) -> list[Chunk]:
        strategy = self.detect_strategy(meta=meta, text=text)

        if self.contextual_enabled and self.llm_provider:
            from app.services.chunking.contextual import ContextualChunking
            strategy = ContextualChunking(
                self.llm_provider, strategy, max_doc_chars=self.max_doc_chars,
            )

        return await strategy.chunk(text, meta)
