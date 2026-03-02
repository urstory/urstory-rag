"""CascadingQualityEvaluator 단위 테스트."""
from __future__ import annotations

import uuid

import pytest

from app.models.schemas import SearchResult
from app.services.search.cascading_evaluator import (
    CascadingEvalResult,
    CascadingQualityEvaluator,
)

DOC_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a1")


def _make_result(score: float) -> SearchResult:
    return SearchResult(
        chunk_id=uuid.uuid4(),
        document_id=DOC_ID,
        content="테스트 문서",
        score=score,
    )


@pytest.fixture
def evaluator():
    return CascadingQualityEvaluator(
        threshold=3.0,
        min_qualifying_docs=3,
        min_doc_score=1.0,
    )


class TestCascadingQualityEvaluator:

    def test_sufficient_when_high_score_and_enough_docs(self, evaluator):
        """높은 점수 + 충분한 유효 문서 → sufficient=True."""
        results = [_make_result(8.0), _make_result(5.0), _make_result(3.0), _make_result(0.5)]
        eval_result = evaluator.evaluate(results)

        assert eval_result.sufficient is True
        assert eval_result.top_score == 8.0
        assert eval_result.qualifying_count == 3

    def test_insufficient_when_low_score(self, evaluator):
        """낮은 top_score → sufficient=False."""
        results = [_make_result(0.5), _make_result(0.3), _make_result(0.1)]
        eval_result = evaluator.evaluate(results)

        assert eval_result.sufficient is False
        assert eval_result.top_score == 0.5

    def test_insufficient_when_few_qualifying_docs(self, evaluator):
        """top_score 높지만 유효 문서 수 부족 → sufficient=False."""
        results = [_make_result(5.0), _make_result(0.5), _make_result(0.3)]
        eval_result = evaluator.evaluate(results)

        assert eval_result.sufficient is False
        assert eval_result.qualifying_count == 1  # 5.0만 ≥ 1.0

    def test_empty_results(self, evaluator):
        """빈 결과 → sufficient=False."""
        eval_result = evaluator.evaluate([])

        assert eval_result.sufficient is False
        assert eval_result.top_score == 0.0
        assert eval_result.qualifying_count == 0

    def test_threshold_boundary_exact(self, evaluator):
        """임계값 정확히 일치 시 sufficient=True."""
        results = [_make_result(3.0), _make_result(2.0), _make_result(1.5)]
        eval_result = evaluator.evaluate(results)

        assert eval_result.sufficient is True
        assert eval_result.qualifying_count == 3

    def test_custom_threshold(self):
        """커스텀 임계값 동작 확인."""
        evaluator = CascadingQualityEvaluator(
            threshold=10.0,
            min_qualifying_docs=1,
            min_doc_score=0.5,
        )
        results = [_make_result(5.0), _make_result(3.0)]
        eval_result = evaluator.evaluate(results)

        assert eval_result.sufficient is False  # 5.0 < 10.0
