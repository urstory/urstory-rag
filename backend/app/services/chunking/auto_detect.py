"""자동 감지 청킹: 파일 타입과 텍스트 구조로 전략 선택."""
import re

from app.services.chunking.base import Chunk, ChunkingStrategy
from app.services.chunking.recursive import RecursiveChunking


class AutoDetectChunking:
    """파일 타입, 평균 문단 길이, 섹션 구조를 분석하여 전략 자동 선택."""

    def detect_strategy(self, meta: dict | None = None, text: str = "") -> ChunkingStrategy:
        file_type = (meta or {}).get("file_type", "txt")

        # 마크다운: 섹션 구조가 있으면 더 큰 청크 사용
        if file_type == "md":
            headings = len(re.findall(r'^#{1,6}\s', text, re.MULTILINE))
            if headings >= 3:
                return RecursiveChunking(chunk_size=1024, chunk_overlap=100)
            return RecursiveChunking(chunk_size=512, chunk_overlap=50)

        # PDF: 보통 긴 문서이므로 큰 청크
        if file_type == "pdf":
            return RecursiveChunking(chunk_size=1024, chunk_overlap=100)

        # 기본: recursive
        return RecursiveChunking(chunk_size=512, chunk_overlap=50)

    async def chunk(self, text: str, meta: dict | None = None) -> list[Chunk]:
        strategy = self.detect_strategy(meta=meta, text=text)
        return await strategy.chunk(text, meta)
