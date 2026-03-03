"""리랭킹 서비스 추상 인터페이스."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.models.schemas import SearchResult


@runtime_checkable
class Reranker(Protocol):
    """리랭커 Protocol.

    초기 검색 결과를 query-document 관련성 점수로 재정렬하여
    가장 관련성 높은 문서를 상위에 배치한다.
    """

    async def rerank(
        self,
        query: str,
        documents: list[SearchResult],
        top_k: int = 5,
        score_mode: str = "calibrated",
        alpha: float = 0.7,
    ) -> list[SearchResult]: ...
