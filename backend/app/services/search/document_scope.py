"""문서 단위 후보 선택: 청크를 문서별로 그룹핑 후 상위 N개 문서만 남긴다.

리랭킹 전 엉뚱한 문서에서 온 청크를 사전에 필터링하여
오참조(wrong document reference) 문제를 줄인다.
"""
from __future__ import annotations

from collections import defaultdict

from app.models.schemas import SearchResult


class DocumentScopeSelector:
    """문서 단위 후보 선택기.

    1. 청크를 document_id로 그룹핑
    2. 각 문서의 대표 점수 = 해당 문서 청크 중 max score
    3. 대표 점수 기준 상위 top_n 문서만 남김
    4. 남은 문서들의 청크만 반환
    """

    def __init__(self, top_n: int = 3) -> None:
        self.top_n = top_n

    def select(self, documents: list[SearchResult]) -> list[SearchResult]:
        """상위 N개 문서에 속하는 청크만 필터링한다."""
        if not documents:
            return []

        # document_id별 그룹핑
        groups: dict[str, list[SearchResult]] = defaultdict(list)
        for doc in documents:
            groups[str(doc.document_id)].append(doc)

        # 문서 수가 top_n 이하면 필터링 불필요
        if len(groups) <= self.top_n:
            return documents

        # 각 문서의 대표 점수 (max score)
        doc_scores: list[tuple[str, float]] = []
        for doc_id, chunks in groups.items():
            max_score = max(c.score for c in chunks)
            doc_scores.append((doc_id, max_score))

        # 상위 N개 문서 선택
        doc_scores.sort(key=lambda x: x[1], reverse=True)
        top_doc_ids = {doc_id for doc_id, _ in doc_scores[:self.top_n]}

        # 선택된 문서의 청크만 반환 (원래 순서 유지)
        return [d for d in documents if str(d.document_id) in top_doc_ids]
