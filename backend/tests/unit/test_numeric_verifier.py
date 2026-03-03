"""NumericVerifier 단위 테스트: 답변 내 숫자 검증 가드레일."""
from __future__ import annotations

import pytest

from app.services.guardrails.numeric_verifier import NumericVerifier, NumericVerification


@pytest.fixture
def verifier():
    return NumericVerifier()


class TestNumericVerifier:

    def test_all_numbers_in_context_passes(self, verifier):
        """답변의 모든 숫자가 컨텍스트에 있으면 PASS."""
        answer = "반기별 1회 이상 정기적으로 실시해야 합니다."
        context = ["반기별 1회 이상 정기적으로 실시해야 합니다."]

        result = verifier.verify(answer, context)

        assert result.passed is True

    def test_number_not_in_context_fails(self, verifier):
        """'연 1회'가 답변에 있지만 컨텍스트엔 '반기별 1회'만 있으면 FAIL."""
        answer = "연 1회 이상 실시해야 합니다."
        context = ["반기별 1회 이상 정기적으로 실시해야 합니다."]

        result = verifier.verify(answer, context)

        assert result.passed is False
        assert len(result.ungrounded_numbers) > 0

    def test_equivalent_terms_pass(self, verifier):
        """'반기'가 컨텍스트에 있고 '6개월'이 답변에 있으면 동등어로 PASS."""
        answer = "6개월마다 1회 실시합니다."
        context = ["반기별 1회 이상 정기적으로 실시해야 합니다."]

        result = verifier.verify(answer, context)

        assert result.passed is True

    def test_no_numbers_in_answer_passes(self, verifier):
        """답변에 도메인 숫자가 없으면 검증 스킵하고 PASS."""
        answer = "장기요양이란 고령이나 노인성 질병으로 일상생활을 혼자 수행하기 어려운 상태입니다."
        context = ["장기요양 관련 설명 문서"]

        result = verifier.verify(answer, context)

        assert result.passed is True
        assert result.total_numbers_found == 0

    def test_ungrounded_numbers_listed(self, verifier):
        """근거 없는 숫자 표현이 목록으로 반환된다."""
        answer = "교육은 연 2회, 점검은 분기별 1회 실시합니다."
        context = ["교육은 연 3회 실시한다."]

        result = verifier.verify(answer, context)

        assert result.passed is False
        assert any("2회" in n or "1회" in n for n in result.ungrounded_numbers)

    def test_comma_separated_numbers_normalized(self, verifier):
        """'1,000원'과 '1000원'이 동일하게 처리된다."""
        answer = "지원금은 1,000원입니다."
        context = ["지원금은 1000원이다."]

        result = verifier.verify(answer, context)

        assert result.passed is True

    def test_non_domain_numbers_ignored(self, verifier):
        """도메인 단위가 없는 숫자는 검증 대상에서 제외된다."""
        answer = "제3장에서 설명하는 내용입니다."
        context = ["다른 문서 내용"]

        result = verifier.verify(answer, context)

        # "제3장"은 도메인 숫자+단위가 아니므로 검증 대상이 아님
        assert result.passed is True
