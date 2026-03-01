"""Step 4.4: Reciprocal Rank Fusion (RRF) — 벡터 + 키워드 검색 결과 결합."""
from __future__ import annotations

import uuid

from app.models.schemas import SearchResult


class RRFCombiner:
    """Reciprocal Rank Fusion으로 벡터 + 키워드 검색 결과를 결합한다.

    RRF 공식: score(d) = Σ weight_i / (k + rank_i + 1)

    각 검색 리스트에서 문서의 순위(rank)를 기반으로 스코어를 계산하고,
    동일 문서가 여러 리스트에 등장하면 스코어를 합산한다.

    Args:
        k: 순위 상수 (기본 60). 값이 클수록 순위 차이의 영향이 줄어듦.
    """

    def combine(
        self,
        vector_results: list[SearchResult],
        keyword_results: list[SearchResult],
        k: int = 60,
        vector_weight: float = 0.5,
        keyword_weight: float = 0.5,
    ) -> list[SearchResult]:
        """벡터 검색 결과와 키워드 검색 결과를 RRF로 결합한다.

        Args:
            vector_results: 벡터 검색 결과 (유사도 순 정렬).
            keyword_results: 키워드 검색 결과 (관련도 순 정렬).
            k: RRF 상수. 순위 차이에 대한 민감도를 조절한다.
            vector_weight: 벡터 검색 결과에 대한 가중치.
            keyword_weight: 키워드 검색 결과에 대한 가중치.

        Returns:
            RRF 스코어 내림차순으로 정렬된 결합 결과 리스트.
        """
        scores: dict[uuid.UUID, float] = {}
        doc_map: dict[uuid.UUID, SearchResult] = {}

        # 벡터 검색 결과의 RRF 스코어 계산
        for rank, result in enumerate(vector_results):
            rrf_score = vector_weight / (k + rank + 1)
            scores[result.chunk_id] = scores.get(result.chunk_id, 0.0) + rrf_score
            doc_map[result.chunk_id] = result

        # 키워드 검색 결과의 RRF 스코어 계산
        for rank, result in enumerate(keyword_results):
            rrf_score = keyword_weight / (k + rank + 1)
            scores[result.chunk_id] = scores.get(result.chunk_id, 0.0) + rrf_score
            if result.chunk_id not in doc_map:
                doc_map[result.chunk_id] = result

        # RRF 스코어를 적용한 결과 리스트 생성 및 내림차순 정렬
        combined: list[SearchResult] = []
        for chunk_id, rrf_score in scores.items():
            original = doc_map[chunk_id]
            combined.append(
                SearchResult(
                    chunk_id=original.chunk_id,
                    document_id=original.document_id,
                    content=original.content,
                    score=rrf_score,
                    metadata=original.metadata,
                )
            )

        combined.sort(key=lambda r: r.score, reverse=True)
        return combined
