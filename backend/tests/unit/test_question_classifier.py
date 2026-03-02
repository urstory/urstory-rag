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


class TestExtractionClassification:
    """extraction 카테고리 분류 테스트."""

    def test_name_question_classified_as_extraction(self, classifier):
        """'이름은 무엇' 형태는 extraction으로 분류된다."""
        result = classifier.classify("기본 내장된 세 가지 서브에이전트의 이름은 무엇인가요?")
        assert result.category == "extraction"

    def test_designation_question_classified_as_extraction(self, classifier):
        """'무엇이라고 부르나' 형태는 extraction으로 분류된다."""
        result = classifier.classify("이 클래스를 무엇이라고 부르나요?")
        assert result.category == "extraction"

    def test_default_value_question_classified_as_extraction(self, classifier):
        """'기본값' 질문은 extraction으로 분류된다."""
        result = classifier.classify("캐시의 기본 값은 무엇인가요?")
        assert result.category == "extraction"

    def test_enumeration_question_classified_as_extraction(self, classifier):
        """'다섯 가지 계층' 형태는 extraction으로 분류된다."""
        result = classifier.classify("AI 에이전트 인프라를 구성하는 다섯 가지 계층은 무엇인가요?")
        assert result.category == "extraction"

    def test_extraction_takes_priority_over_regulatory(self, classifier):
        """extraction 패턴이 regulatory보다 우선한다."""
        result = classifier.classify("세 가지 기준 점수의 명칭은 무엇인가요?")
        assert result.category == "extraction"

    def test_pure_number_question_stays_regulatory(self, classifier):
        """순수 숫자 질문은 여전히 regulatory."""
        result = classifier.classify("평가 점수는 몇 점인가요?")
        assert result.category == "regulatory"

    def test_builtin_list_question(self, classifier):
        """'내장된 ... 이름' 패턴은 extraction."""
        result = classifier.classify("Claude Code에 내장된 서브에이전트 이름은?")
        assert result.category == "extraction"
