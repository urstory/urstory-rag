"""검색 품질 게이트: 검색된 문서의 관련성을 점수 기반으로 평가.

soft_mode가 활성화되면 점수 기준 미달 시 즉시 차단하지 않고
soft_fail을 반환하여 근거 추출 시도 기회를 제공한다.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.models.schemas import SearchResult


@dataclass
class RetrievalGateResult:
    passed: bool = True
    soft_fail: bool = False
    top_score: float = 0.0
    qualifying_count: int = 0
    reason: str | None = None


class RetrievalQualityGate:
    """점수 기반 검색 품질 게이트.

    리랭킹 후 문서의 관련성 점수를 평가하여
    기준 미달 시 답변 생성을 건너뛴다.

    soft_mode=True이면 점수 미달을 soft_fail로 처리하여
    오케스트레이터가 근거 추출을 시도한 뒤 최종 판정할 수 있게 한다.
    """

    def __init__(
        self,
        min_top_score: float = 0.05,
        min_doc_count: int = 1,
        min_doc_score: float = 0.1,
        soft_mode: bool = True,
    ) -> None:
        self.min_top_score = min_top_score
        self.min_doc_count = min_doc_count
        self.min_doc_score = min_doc_score
        self.soft_mode = soft_mode

    def evaluate(self, documents: list[SearchResult]) -> RetrievalGateResult:
        """검색 결과의 품질을 평가한다."""
        if not documents:
            return RetrievalGateResult(
                passed=False,
                top_score=0.0,
                qualifying_count=0,
                reason="no_documents",
            )

        top_score = documents[0].score
        qualifying = [d for d in documents if d.score >= self.min_doc_score]
        qualifying_count = len(qualifying)

        if top_score < self.min_top_score:
            return RetrievalGateResult(
                passed=False,
                soft_fail=self.soft_mode,
                top_score=top_score,
                qualifying_count=qualifying_count,
                reason=f"top_score({top_score:.3f}) < min({self.min_top_score})",
            )

        if qualifying_count < self.min_doc_count:
            return RetrievalGateResult(
                passed=False,
                soft_fail=self.soft_mode,
                top_score=top_score,
                qualifying_count=qualifying_count,
                reason=f"qualifying_docs({qualifying_count}) < min({self.min_doc_count})",
            )

        return RetrievalGateResult(
            passed=True,
            top_score=top_score,
            qualifying_count=qualifying_count,
        )
