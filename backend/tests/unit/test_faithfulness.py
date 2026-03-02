"""충실도 검증 단위 테스트."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.services.guardrails.faithfulness import FaithfulnessChecker, FaithfulnessResult


@pytest.fixture
def mock_llm():
    return AsyncMock()


class TestFaithfulnessChecker:
    """충실도 검증기 단위 테스트."""

    @pytest.mark.asyncio
    async def test_faithful_answer_passes(self, mock_llm):
        """충실한 답변 → FAITHFUL."""
        mock_llm.generate.return_value = (
            "faithfulness_score: 0.95\n"
            "distortions: []\n"
            "verdict: FAITHFUL"
        )
        checker = FaithfulnessChecker(llm=mock_llm, threshold=0.9)
        result = await checker.verify("정확한 답변", ["원문 문서"])

        assert result.verdict == "FAITHFUL"
        assert result.faithfulness_score == 0.95
        assert result.distortions == []

    @pytest.mark.asyncio
    async def test_distorted_number_detected(self, mock_llm):
        """숫자 왜곡 → UNFAITHFUL."""
        mock_llm.generate.return_value = (
            "faithfulness_score: 0.6\n"
            "distortions: ['원문: 130만 포인트 → 답변: 100만 이상']\n"
            "verdict: UNFAITHFUL"
        )
        checker = FaithfulnessChecker(llm=mock_llm, threshold=0.9)
        result = await checker.verify("100만 이상 포인트", ["130만 포인트 적립"])

        assert result.verdict == "UNFAITHFUL"
        assert result.faithfulness_score == 0.6
        assert len(result.distortions) >= 1

    @pytest.mark.asyncio
    async def test_distorted_frequency_detected(self, mock_llm):
        """주기/빈도 왜곡 → UNFAITHFUL."""
        mock_llm.generate.return_value = (
            "faithfulness_score: 0.5\n"
            "distortions: ['원문: 반기별 1회 → 답변: 연 1회']\n"
            "verdict: UNFAITHFUL"
        )
        checker = FaithfulnessChecker(llm=mock_llm, threshold=0.9)
        result = await checker.verify("연 1회 평가", ["반기별 1회 평가"])

        assert result.verdict == "UNFAITHFUL"
        assert result.faithfulness_score == 0.5

    def test_parse_result_valid(self):
        """정상 LLM 응답 파싱."""
        response = (
            "faithfulness_score: 0.85\n"
            "distortions: ['원문: 주 3회 → 답변: 주 2회']\n"
            "verdict: UNFAITHFUL"
        )
        result = FaithfulnessChecker._parse_result(response)
        assert result.faithfulness_score == 0.85
        assert len(result.distortions) == 1
        assert "주 3회" in result.distortions[0]
        assert result.verdict == "UNFAITHFUL"

    def test_parse_result_malformed(self):
        """비정상 응답 → 기본값 (충실로 간주)."""
        response = "알 수 없는 형식의 응답입니다."
        result = FaithfulnessChecker._parse_result(response)
        assert result.faithfulness_score == 1.0
        assert result.distortions == []
        assert result.verdict == "FAITHFUL"

    def test_handle_result_warn(self):
        """warn → 경고 추가."""
        result = FaithfulnessResult(
            faithfulness_score=0.6,
            distortions=["원문: 130만 → 답변: 100만"],
            verdict="UNFAITHFUL",
        )
        answer = FaithfulnessChecker.handle_result("원래 답변", result, action="warn")
        assert "원래 답변" in answer
        assert "⚠️" in answer
        assert "충실도" in answer
        assert "130만" in answer

    def test_handle_result_block(self):
        """block → 차단 메시지."""
        result = FaithfulnessResult(
            faithfulness_score=0.3,
            distortions=["왜곡"],
            verdict="UNFAITHFUL",
        )
        answer = FaithfulnessChecker.handle_result("원래 답변", result, action="block")
        assert "원래 답변" not in answer
        assert "정확성을 보장할 수 없습니다" in answer

    def test_handle_result_faithful_unchanged(self):
        """FAITHFUL → 원본 유지."""
        result = FaithfulnessResult(
            faithfulness_score=0.95,
            distortions=[],
            verdict="FAITHFUL",
        )
        answer = FaithfulnessChecker.handle_result("원래 답변", result, action="warn")
        assert answer == "원래 답변"
