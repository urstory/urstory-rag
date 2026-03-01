"""PGVector 기반 벡터 검색 엔진.

Step 4.1: cosine distance (<=> 연산자)를 사용한 유사도 검색.
Score = 1 - cosine_distance (높을수록 유사).
"""
from __future__ import annotations

import uuid

from sqlalchemy import text

from app.exceptions import SearchServiceError
from app.models.schemas import SearchResult


class VectorSearchEngine:
    """PGVector 기반 벡터 검색 엔진.

    Args:
        session_factory: SQLAlchemy async_sessionmaker 인스턴스.
            async with session_factory() as session 패턴으로 사용.
    """

    # doc_id 필터 없는 기본 쿼리
    _BASE_SQL = text(
        """
        SELECT
            c.id AS chunk_id,
            c.document_id,
            c.content,
            c.embedding <=> :query_embedding AS distance,
            c.metadata
        FROM chunks c
        ORDER BY distance ASC
        LIMIT :top_k
        """
    )

    # doc_id 필터 포함 쿼리
    _FILTERED_SQL = text(
        """
        SELECT
            c.id AS chunk_id,
            c.document_id,
            c.content,
            c.embedding <=> :query_embedding AS distance,
            c.metadata
        FROM chunks c
        WHERE c.document_id = :doc_id
        ORDER BY distance ASC
        LIMIT :top_k
        """
    )

    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    async def search(
        self,
        query_embedding: list[float],
        top_k: int = 20,
        doc_id: uuid.UUID | None = None,
    ) -> list[SearchResult]:
        """벡터 유사도 검색을 수행한다.

        Args:
            query_embedding: 쿼리 임베딩 벡터.
            top_k: 반환할 최대 결과 수.
            doc_id: 특정 문서 ID로 필터링 (선택).

        Returns:
            유사도 점수 내림차순으로 정렬된 SearchResult 리스트.

        Raises:
            SearchServiceError: DB 쿼리 실패 시.
        """
        try:
            async with self.session_factory() as session:
                # 쿼리 파라미터 구성
                embedding_str = f"[{','.join(str(v) for v in query_embedding)}]"
                params: dict = {
                    "query_embedding": embedding_str,
                    "top_k": top_k,
                }

                if doc_id is not None:
                    query = self._FILTERED_SQL
                    params["doc_id"] = str(doc_id)
                else:
                    query = self._BASE_SQL

                result = await session.execute(query, params=params)
                rows = result.fetchall()

                return [
                    SearchResult(
                        chunk_id=row.chunk_id,
                        document_id=row.document_id,
                        content=row.content,
                        score=1.0 - row.distance,
                        metadata=row.metadata,
                    )
                    for row in rows
                ]

        except SearchServiceError:
            raise
        except Exception as exc:
            raise SearchServiceError(f"벡터 검색 실패: {exc}") from exc
