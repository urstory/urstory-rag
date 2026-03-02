"""DocumentScopeSelector 단위 테스트."""
from __future__ import annotations

import uuid

import pytest

from app.models.schemas import SearchResult
from app.services.search.document_scope import DocumentScopeSelector

DOC_A = uuid.UUID("00000000-0000-0000-0000-000000000001")
DOC_B = uuid.UUID("00000000-0000-0000-0000-000000000002")
DOC_C = uuid.UUID("00000000-0000-0000-0000-000000000003")
DOC_D = uuid.UUID("00000000-0000-0000-0000-000000000004")


def _make(doc_id: uuid.UUID, score: float, content: str = "test") -> SearchResult:
    return SearchResult(
        chunk_id=uuid.uuid4(),
        document_id=doc_id,
        content=content,
        score=score,
    )


class TestDocumentScopeSelector:

    def test_empty_returns_empty(self):
        selector = DocumentScopeSelector(top_n=3)
        assert selector.select([]) == []

    def test_fewer_docs_than_top_n_returns_all(self):
        """문서 수 < top_n이면 전체 반환."""
        docs = [_make(DOC_A, 0.9), _make(DOC_B, 0.7)]
        selector = DocumentScopeSelector(top_n=3)
        result = selector.select(docs)
        assert len(result) == 2

    def test_selects_top_n_documents(self):
        """4개 문서 중 top_n=2 → 상위 2개 문서 청크만 남김."""
        docs = [
            _make(DOC_A, 0.9),
            _make(DOC_B, 0.7),
            _make(DOC_C, 0.5),
            _make(DOC_D, 0.3),
        ]
        selector = DocumentScopeSelector(top_n=2)
        result = selector.select(docs)

        result_doc_ids = {str(d.document_id) for d in result}
        assert str(DOC_A) in result_doc_ids
        assert str(DOC_B) in result_doc_ids
        assert str(DOC_C) not in result_doc_ids
        assert str(DOC_D) not in result_doc_ids

    def test_uses_max_score_per_document(self):
        """동일 문서의 여러 청크 → max score로 대표 점수 결정."""
        docs = [
            _make(DOC_A, 0.2),  # DOC_A의 낮은 청크
            _make(DOC_A, 0.9),  # DOC_A의 높은 청크 → 대표 점수 0.9
            _make(DOC_B, 0.5),
            _make(DOC_C, 0.4),
            _make(DOC_D, 0.3),
        ]
        selector = DocumentScopeSelector(top_n=2)
        result = selector.select(docs)

        result_doc_ids = {str(d.document_id) for d in result}
        assert str(DOC_A) in result_doc_ids  # max 0.9
        assert str(DOC_B) in result_doc_ids  # 0.5

    def test_preserves_all_chunks_of_selected_docs(self):
        """선택된 문서의 모든 청크가 유지된다."""
        docs = [
            _make(DOC_A, 0.9),
            _make(DOC_A, 0.8),
            _make(DOC_A, 0.7),
            _make(DOC_B, 0.6),
            _make(DOC_C, 0.5),
        ]
        selector = DocumentScopeSelector(top_n=2)
        result = selector.select(docs)

        doc_a_chunks = [d for d in result if d.document_id == DOC_A]
        assert len(doc_a_chunks) == 3  # DOC_A의 3개 청크 모두 유지

    def test_preserves_original_order(self):
        """원래 점수 순서가 유지된다."""
        docs = [
            _make(DOC_A, 0.9),
            _make(DOC_B, 0.7),
            _make(DOC_C, 0.5),
            _make(DOC_A, 0.3),
        ]
        selector = DocumentScopeSelector(top_n=2)
        result = selector.select(docs)

        scores = [d.score for d in result]
        assert scores == sorted(scores, reverse=True)
