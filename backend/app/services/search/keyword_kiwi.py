"""Step 4.3: kiwipiepy + BM25 인메모리 키워드 검색 엔진 (Elasticsearch 대안).

kiwipiepy 형태소 분석기와 rank_bm25 라이브러리를 결합하여
Elasticsearch + Nori 분석기 없이도 한국어 키워드 검색을 수행할 수 있다.

사용 시나리오:
  - Elasticsearch를 띄울 수 없는 경량 환경
  - 관리자 UI에서 keyword_engine = "kiwi_bm25" 선택 시 활성화
"""
from __future__ import annotations

import uuid

from kiwipiepy import Kiwi
from rank_bm25 import BM25Okapi

from app.models.schemas import SearchResult

# kiwipiepy 품사 태그 중 검색에 유의미한 태그 접두사
# N*: 명사(NNG, NNP, NNB, NR, NP 등)
# V*: 동사(VV, VA, VX, VCP, VCN 등)
# XR: 형용사 어근
_KEEP_TAG_PREFIXES = ("N", "V", "XR")


class KiwipieyyBM25Engine:
    """kiwipiepy + BM25Okapi 인메모리 키워드 검색 엔진.

    Elasticsearch 대안으로, 소규모 문서 컬렉션에 대해
    한국어 형태소 분석 기반 BM25 검색을 제공한다.
    """

    def __init__(self) -> None:
        self.kiwi = Kiwi()
        self.bm25: BM25Okapi | None = None
        self.documents: list[dict] = []

    # ------------------------------------------------------------------
    # 토큰화
    # ------------------------------------------------------------------

    def _tokenize(self, text: str) -> list[str]:
        """kiwipiepy 형태소 분석 후 명사/동사/형용사 어근만 추출.

        Args:
            text: 분석할 한국어 텍스트.

        Returns:
            유의미한 형태소(명사, 동사, 형용사 어근) 리스트.
        """
        if not text or not text.strip():
            return []

        tokens = self.kiwi.tokenize(text)
        return [
            t.form
            for t in tokens
            if t.tag.startswith(_KEEP_TAG_PREFIXES)
        ]

    # ------------------------------------------------------------------
    # 인덱스 구축
    # ------------------------------------------------------------------

    def build_index(self, documents: list[dict]) -> None:
        """문서 리스트로 BM25 인덱스를 구축한다.

        Args:
            documents: 각 원소는 다음 키를 포함하는 딕셔너리:
                - chunk_id (uuid.UUID): 청크 고유 ID
                - document_id (uuid.UUID): 소속 문서 ID
                - content (str): 청크 텍스트
                - metadata (dict | None): 부가 메타데이터
        """
        self.documents = documents

        if not documents:
            self.bm25 = None
            return

        tokenized_corpus = [self._tokenize(doc["content"]) for doc in documents]
        self.bm25 = BM25Okapi(tokenized_corpus)

    # ------------------------------------------------------------------
    # 검색
    # ------------------------------------------------------------------

    async def search(
        self,
        query: str,
        top_k: int = 20,
        doc_id: str | None = None,
    ) -> list[SearchResult]:
        """BM25 기반 키워드 검색을 수행한다.

        Args:
            query: 검색 질의 텍스트.
            top_k: 반환할 최대 결과 수.
            doc_id: 특정 문서 ID로 필터링 (선택).

        Returns:
            BM25 점수 내림차순으로 정렬된 SearchResult 리스트.
            점수가 0인 결과는 제외된다.
        """
        if self.bm25 is None or not self.documents:
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        scores = self.bm25.get_scores(query_tokens)

        # (인덱스, 점수) 쌍 생성 후 점수 내림차순 정렬
        scored_indices = sorted(
            enumerate(scores),
            key=lambda x: x[1],
            reverse=True,
        )

        results: list[SearchResult] = []
        for idx, score in scored_indices:
            # 점수 0 이하인 문서는 제외
            if score <= 0.0:
                break

            doc = self.documents[idx]

            # doc_id 필터 적용
            if doc_id is not None:
                if str(doc["document_id"]) != doc_id:
                    continue

            results.append(
                SearchResult(
                    chunk_id=doc["chunk_id"],
                    document_id=doc["document_id"],
                    content=doc["content"],
                    score=float(score),
                    metadata=doc.get("metadata"),
                )
            )

            if len(results) >= top_k:
                break

        return results
