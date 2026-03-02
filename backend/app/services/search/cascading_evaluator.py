"""Cascading 품질 평가: BM25 검색 결과의 충분성을 판정한다."""
from __future__ import annotations

from dataclasses import dataclass

from app.models.schemas import SearchResult


@dataclass
class CascadingEvalResult:
    sufficient: bool = False
    top_score: float = 0.0
    qualifying_count: int = 0


class CascadingQualityEvaluator:
    """BM25 결과의 품질을 평가하여 다음 단계 진행 여부를 결정.

    ES BM25 score는 0~∞ 범위이며, 문서/쿼리에 따라 차이가 큼.
    threshold와 min_qualifying_docs를 조합하여 판정.
    """

    def __init__(
        self,
        threshold: float = 3.0,
        min_qualifying_docs: int = 3,
        min_doc_score: float = 1.0,
    ) -> None:
        self.threshold = threshold
        self.min_qualifying_docs = min_qualifying_docs
        self.min_doc_score = min_doc_score

    def evaluate(self, results: list[SearchResult]) -> CascadingEvalResult:
        """검색 결과의 품질을 평가한다."""
        if not results:
            return CascadingEvalResult(sufficient=False, top_score=0.0, qualifying_count=0)

        top_score = results[0].score
        qualifying = [r for r in results if r.score >= self.min_doc_score]
        qualifying_count = len(qualifying)

        sufficient = (
            top_score >= self.threshold
            and qualifying_count >= self.min_qualifying_docs
        )

        return CascadingEvalResult(
            sufficient=sufficient,
            top_score=top_score,
            qualifying_count=qualifying_count,
        )
