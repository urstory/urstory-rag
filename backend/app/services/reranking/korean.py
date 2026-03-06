"""한국어 특화 Cross-Encoder 리랭커."""
from __future__ import annotations

import math

from sentence_transformers import CrossEncoder

from app.models.schemas import SearchResult


def _sigmoid(x: float) -> float:
    """Numerically stable sigmoid function."""
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    exp_x = math.exp(x)
    return exp_x / (1.0 + exp_x)


class KoreanCrossEncoder:
    """dragonkue/bge-reranker-v2-m3-ko 기반 한국어 리랭커.

    한국어 AutoRAG 벤치마크 F1=0.9123 전체 1위 모델.
    cross-encoder/ms-marco-MiniLM은 영어 전용이므로 사용 금지.

    Device 선택은 sentence-transformers가 자동 처리
    (MPS/CUDA/CPU 순으로 탐색).

    Score Modes:
    - "calibrated": sigmoid(CE logit) + rank signal 결합 (권장)
    - "replace": 기존 동작 (raw logit으로 점수 교체)
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
        score_mode: str = "calibrated",
        alpha: float = 0.7,
    ) -> list[SearchResult]:
        """query-document 쌍의 관련성 점수로 문서를 재정렬.

        Args:
            query: 사용자 검색 쿼리.
            documents: 초기 검색 결과 리스트.
            top_k: 반환할 상위 문서 수.
            score_mode: 점수 모드.
                - "calibrated": sigmoid 보정 + 순위 신호 결합.
                - "replace": 기존 동작 (raw logit 그대로).
            alpha: calibrated 모드에서 CE 점수 가중치 (0~1).
                final = alpha * sigmoid(logit) + (1-alpha) * rank_score

        Returns:
            점수 기준 내림차순으로 정렬된 상위 top_k개 SearchResult.
        """
        if not documents:
            return []

        # Cross-Encoder 메모리 보호: 입력 텍스트를 512자로 제한
        max_chars = 512
        pairs = [(query, doc.content[:max_chars]) for doc in documents]
        raw_scores = self.model.predict(pairs)

        if score_mode == "replace":
            scored_docs = sorted(
                zip(raw_scores, documents),
                key=lambda x: float(x[0]),
                reverse=True,
            )
            return [
                doc.model_copy(update={"score": float(score)})
                for score, doc in scored_docs[:top_k]
            ]

        # calibrated 모드: sigmoid + rank signal 결합
        # 1. CE logit 기준 정렬하여 rank 할당
        indexed = list(enumerate(raw_scores))
        indexed.sort(key=lambda x: float(x[1]), reverse=True)

        results: list[tuple[float, SearchResult]] = []
        for rank, (orig_idx, logit) in enumerate(indexed):
            ce_prob = _sigmoid(float(logit))
            rank_score = 1.0 / (rank + 1)
            combined = alpha * ce_prob + (1.0 - alpha) * rank_score
            results.append((combined, documents[orig_idx]))

        results.sort(key=lambda x: x[0], reverse=True)

        return [
            doc.model_copy(update={"score": score})
            for score, doc in results[:top_k]
        ]
