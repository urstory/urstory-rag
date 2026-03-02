"""재귀적 문자 분할 청킹 전략 (기본)."""
from haystack.components.preprocessors import DocumentSplitter
from haystack.dataclasses import Document

from app.services.chunking.base import Chunk


class RecursiveChunking:
    """Haystack DocumentSplitter를 래핑한 재귀적 청킹."""

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    async def chunk(self, text: str, meta: dict | None = None) -> list[Chunk]:
        if not text.strip():
            return []

        # 짧은 텍스트는 바로 반환
        if len(text) <= self.chunk_size:
            return [Chunk(content=text, chunk_index=0, metadata=meta or {})]

        # chunk_size에 따라 문장 그룹 크기 조정
        # 1024자 → 약 6문장, 512자 → 약 3문장
        split_length = max(2, self.chunk_size // 170)
        split_overlap = max(1, split_length // 3)

        splitter = DocumentSplitter(
            split_by="sentence",
            split_length=split_length,
            split_overlap=split_overlap,
        )

        doc = Document(content=text, meta=meta or {})
        result = splitter.run(documents=[doc])

        chunks = []
        for i, split_doc in enumerate(result["documents"]):
            if split_doc.content and split_doc.content.strip():
                chunks.append(
                    Chunk(
                        content=split_doc.content.strip(),
                        chunk_index=i,
                        metadata=meta or {},
                    )
                )

        return chunks if chunks else [Chunk(content=text, chunk_index=0, metadata=meta or {})]
