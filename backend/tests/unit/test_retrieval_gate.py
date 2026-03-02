"""검색 품질 게이트 단위 테스트."""
import uuid

import pytest

from app.models.schemas import SearchResult
from app.services.guardrails.retrieval_gate import RetrievalGateResult, RetrievalQualityGate


def _make_result(score: float) -> SearchResult:
    return SearchResult(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        content="테스트 문서",
        score=score,
    )


class TestRetrievalQualityGate:
    """검색 품질 게이트 단위 테스트."""

    def setup_method(self):
        self.gate = RetrievalQualityGate(
            min_top_score=0.3,
            min_doc_count=1,
            min_doc_score=0.1,
        )

    def test_no_documents_fails(self):
        """문서가 없으면 passed=False."""
        result = self.gate.evaluate([])
        assert result.passed is False
        assert result.reason == "no_documents"
        assert result.top_score == 0.0
        assert result.qualifying_count == 0

    def test_low_top_score_fails(self):
        """최상위 점수가 임계값 미만이면 passed=False."""
        docs = [_make_result(0.1), _make_result(0.05)]
        result = self.gate.evaluate(docs)
        assert result.passed is False
        assert "top_score" in result.reason
        assert result.top_score == 0.1

    def test_insufficient_qualifying_docs_fails(self):
        """기준 점수를 넘는 문서 수가 부족하면 passed=False."""
        gate = RetrievalQualityGate(
            min_top_score=0.3,
            min_doc_count=3,
            min_doc_score=0.5,
        )
        docs = [_make_result(0.8), _make_result(0.2), _make_result(0.1)]
        result = gate.evaluate(docs)
        assert result.passed is False
        assert "qualifying_docs" in result.reason
        assert result.qualifying_count == 1

    def test_good_results_passes(self):
        """정상 점수 → passed=True."""
        docs = [_make_result(0.9), _make_result(0.7), _make_result(0.5)]
        result = self.gate.evaluate(docs)
        assert result.passed is True
        assert result.reason is None
        assert result.top_score == 0.9
        assert result.qualifying_count == 3

    def test_exact_threshold_passes(self):
        """경계값(정확히 임계값)은 통과."""
        docs = [_make_result(0.3)]
        result = self.gate.evaluate(docs)
        assert result.passed is True

    def test_just_below_threshold_fails(self):
        """임계값 바로 아래는 실패."""
        docs = [_make_result(0.299)]
        result = self.gate.evaluate(docs)
        assert result.passed is False

    def test_custom_thresholds(self):
        """커스텀 임계값 동작 확인."""
        gate = RetrievalQualityGate(
            min_top_score=0.5,
            min_doc_count=2,
            min_doc_score=0.3,
        )
        docs = [_make_result(0.6), _make_result(0.4), _make_result(0.1)]
        result = gate.evaluate(docs)
        assert result.passed is True
        assert result.qualifying_count == 2
