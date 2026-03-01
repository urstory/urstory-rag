"""한국어 특화 Cross-Encoder 리랭커."""
from __future__ import annotations

from sentence_transformers import CrossEncoder

from app.models.schemas import SearchResult


class KoreanCrossEncoder:
    """dragonkue/bge-reranker-v2-m3-ko 기반 한국어 리랭커.

    한국어 AutoRAG 벤치마크 F1=0.9123 전체 1위 모델.
    cross-encoder/ms-marco-MiniLM은 영어 전용이므로 사용 금지.

    Device 선택은 sentence-transformers가 자동 처리
    (MPS/CUDA/CPU 순으로 탐색).
    """

    def __init__(
        self,
        model_name: str = "dragonkue/bge-reranker-v2-m3-ko",
    ) -> None:
        self.model = CrossEncoder(model_name)

    async def rerank(
        self,
        query: str,
        documents: list[SearchResult],
        top_k: int = 5,
    ) -> list[SearchResult]:
        """query-document 쌍의 관련성 점수로 문서를 재정렬.

        Args:
            query: 사용자 검색 쿼리.
            documents: 초기 검색 결과 리스트.
            top_k: 반환할 상위 문서 수.

        Returns:
            리랭커 점수 기준 내림차순으로 정렬된 상위 top_k개 SearchResult.
        """
        if not documents:
            return []

        pairs = [(query, doc.content) for doc in documents]
        scores = self.model.predict(pairs)

        # (score, doc) 쌍으로 묶어 점수 내림차순 정렬 후 top_k 선택
        scored_docs = sorted(
            zip(scores, documents),
            key=lambda x: float(x[0]),
            reverse=True,
        )

        return [
            doc.model_copy(update={"score": float(score)})
            for score, doc in scored_docs[:top_k]
        ]
