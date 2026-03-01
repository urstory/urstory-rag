"""시맨틱 청킹: 문장별 임베딩 유사도 기반 분할."""
import math
import re

from app.services.chunking.base import Chunk
from app.services.embedding.base import EmbeddingProvider


class SemanticChunking:
    """인접 문장 코사인 유사도가 threshold 이하로 떨어지는 지점에서 분할."""

    def __init__(self, embedding_provider: EmbeddingProvider, threshold: float = 0.5):
        self.embedding_provider = embedding_provider
        self.threshold = threshold

    async def chunk(self, text: str, meta: dict | None = None) -> list[Chunk]:
        if not text.strip():
            return []

        sentences = self._split_sentences(text)
        if len(sentences) <= 1:
            return [Chunk(content=text.strip(), chunk_index=0, metadata=meta or {})]

        # 문장별 임베딩
        embeddings = await self.embedding_provider.embed_documents(sentences)

        # 인접 문장 간 코사인 유사도 계산 → 분할 지점 결정
        split_points = [0]
        for i in range(len(embeddings) - 1):
            sim = self._cosine_similarity(embeddings[i], embeddings[i + 1])
            if sim < self.threshold:
                split_points.append(i + 1)

        # 분할 지점에 따라 청크 생성
        chunks = []
        for idx, start in enumerate(split_points):
            end = split_points[idx + 1] if idx + 1 < len(split_points) else len(sentences)
            content = " ".join(sentences[start:end]).strip()
            if content:
                chunks.append(Chunk(content=content, chunk_index=idx, metadata=meta or {}))

        return chunks

    def _split_sentences(self, text: str) -> list[str]:
        sentences = re.split(r'(?<=[.!?。])\s+', text.strip())
        return [s.strip() for s in sentences if s.strip()]

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)
