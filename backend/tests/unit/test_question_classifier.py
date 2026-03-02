"""QuestionClassifier 단위 테스트: 룰 기반 질문 유형 분류."""
from __future__ import annotations

import pytest

from app.services.search.question_classifier import QuestionClassifier, QuestionType


@pytest.fixture
def classifier():
    return QuestionClassifier()


class TestQuestionClassifier:

    def test_numeric_question_classified_as_regulatory(self, classifier):
        """'몇 회' 포함 질문은 regulatory로 분류된다."""
        result = classifier.classify("평가는 몇 회 실시해야 하나요?")

        assert result.category == "regulatory"
        assert result.confidence > 0

    def test_period_question_classified_as_regulatory(self, classifier):
        """'반기별', '주기' 포함 질문은 regulatory로 분류된다."""
        result = classifier.classify("반기별 점검 주기는 어떻게 되나요?")

        assert result.category == "regulatory"

    def test_general_question_classified_as_explanatory(self, classifier):
        """'~란 무엇인가' 형태는 explanatory로 분류된다."""
        result = classifier.classify("장기요양이란 무엇인가요?")

        assert result.category == "explanatory"

    def test_comparison_question_classified_as_explanatory(self, classifier):
        """비교형 질문은 explanatory로 분류된다."""
        result = classifier.classify("SSH와 Remote Control의 차이점은 무엇인가요?")

        assert result.category == "explanatory"

    def test_mixed_question_with_number_prefers_regulatory(self, classifier):
        """숫자가 포함되면 regulatory가 우선된다."""
        result = classifier.classify("등급 유지 기준 점수는 몇 점인가요?")

        assert result.category == "regulatory"

    def test_indicators_list_contains_matched_patterns(self, classifier):
        """분류 근거 패턴이 indicators에 포함된다."""
        result = classifier.classify("연간 교육 횟수는 몇 회인가요?")

        assert result.category == "regulatory"
        assert len(result.indicators) > 0
