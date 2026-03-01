"""Elasticsearch + Nori 기반 BM25 키워드 검색 엔진."""
from __future__ import annotations

import httpx

from app.exceptions import SearchServiceError
from app.models.schemas import SearchResult


class ElasticsearchNoriEngine:
    """Elasticsearch + Nori 기반 BM25 키워드 검색 엔진.

    Nori 형태소 분석은 인덱스 매핑 레벨에서 설정되므로,
    쿼리 시에는 단순 match 쿼리만 전송하면 된다.
    """

    def __init__(
        self,
        es_url: str = "http://localhost:9200",
        index_name: str = "rag_chunks",
    ) -> None:
        self.es_url = es_url
        self.index_name = index_name

    async def search(
        self,
        query: str,
        top_k: int = 20,
        doc_id: str | None = None,
    ) -> list[SearchResult]:
        """Elasticsearch에 BM25 키워드 검색을 수행한다.

        Args:
            query: 검색 쿼리 (한국어 지원, Nori 분석기가 인덱스 레벨에서 처리)
            top_k: 최대 반환 결과 수
            doc_id: 특정 문서 ID로 필터링 (선택)

        Returns:
            SearchResult 리스트 (score 내림차순)

        Raises:
            SearchServiceError: Elasticsearch 통신 실패 시
        """
        body = self._build_query(query, top_k, doc_id)

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.es_url}/{self.index_name}/_search",
                    json=body,
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()
        except Exception as e:
            raise SearchServiceError(
                f"Elasticsearch keyword search failed: {e}"
            ) from e

        return self._parse_hits(data)

    def _build_query(
        self,
        query: str,
        top_k: int,
        doc_id: str | None,
    ) -> dict:
        """Elasticsearch 쿼리 본문을 생성한다."""
        bool_query: dict = {
            "must": [{"match": {"content": query}}],
            "filter": [],
        }

        if doc_id is not None:
            bool_query["filter"].append({"term": {"document_id": doc_id}})

        return {
            "size": top_k,
            "query": {"bool": bool_query},
        }

    @staticmethod
    def _parse_hits(data: dict) -> list[SearchResult]:
        """ES 응답의 hits를 SearchResult 리스트로 변환한다."""
        hits = data.get("hits", {}).get("hits", [])
        results: list[SearchResult] = []

        for hit in hits:
            source = hit["_source"]
            results.append(
                SearchResult(
                    chunk_id=source["chunk_id"],
                    document_id=source["document_id"],
                    content=source["content"],
                    score=hit["_score"],
                    metadata=source.get("metadata"),
                )
            )

        return results
