"""Step 5.5: 할루시네이션 탐지 단위 테스트."""
from unittest.mock import AsyncMock

import pytest

from app.services.guardrails.hallucination import HallucinationDetector, HallucinationResult


class TestHallucinationDetector:

    @pytest.mark.asyncio
    async def test_hallucination_pass(self):
        """근거 있는 답변 → PASS."""
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = (
            "grounded_ratio: 0.95\n"
            "ungrounded_claims: []\n"
            "verdict: PASS"
        )
        detector = HallucinationDetector(llm=mock_llm)
        result = await detector.verify(
            answer="한국의 GDP는 1.7조 달러입니다.",
            documents=["한국의 GDP는 약 1.7조 달러 규모이다."],
        )
        assert result.verdict == "PASS"
        assert result.grounded_ratio >= 0.8

    @pytest.mark.asyncio
    async def test_hallucination_fail(self):
        """근거 없는 답변 → FAIL."""
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = (
            "grounded_ratio: 0.3\n"
            "ungrounded_claims: ['한국이 세계 1위 경제대국이다']\n"
            "verdict: FAIL"
        )
        detector = HallucinationDetector(llm=mock_llm)
        result = await detector.verify(
            answer="한국이 세계 1위 경제대국이다.",
            documents=["한국은 GDP 기준 세계 13위 경제국이다."],
        )
        assert result.verdict == "FAIL"
        assert result.grounded_ratio < 0.8
        assert len(result.ungrounded_claims) > 0

    @pytest.mark.asyncio
    async def test_hallucination_warn_action(self):
        """warn 액션 시 경고 메시지 추가."""
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = (
            "grounded_ratio: 0.5\n"
            "ungrounded_claims: ['근거 없는 주장']\n"
            "verdict: FAIL"
        )
        detector = HallucinationDetector(llm=mock_llm)
        result = await detector.verify(
            answer="테스트 답변",
            documents=["테스트 문서"],
        )
        handled = detector.handle_result("테스트 답변", result, action="warn")
        assert "확인되지 않았습니다" in handled or "경고" in handled.lower() or "⚠" in handled

    @pytest.mark.asyncio
    async def test_hallucination_block_action(self):
        """block 액션 시 답변 차단."""
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = (
            "grounded_ratio: 0.2\n"
            "ungrounded_claims: ['모든 주장 근거 없음']\n"
            "verdict: FAIL"
        )
        detector = HallucinationDetector(llm=mock_llm)
        result = await detector.verify(
            answer="원본 답변",
            documents=["문서"],
        )
        handled = detector.handle_result("원본 답변", result, action="block")
        assert "원본 답변" not in handled
        assert "생성할 수 없습니다" in handled or "차단" in handled

    @pytest.mark.asyncio
    async def test_hallucination_pass_returns_original(self):
        """PASS일 때는 원본 답변 그대로 반환."""
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = (
            "grounded_ratio: 0.9\n"
            "ungrounded_claims: []\n"
            "verdict: PASS"
        )
        detector = HallucinationDetector(llm=mock_llm)
        result = await detector.verify(
            answer="정확한 답변",
            documents=["정확한 문서"],
        )
        handled = detector.handle_result("정확한 답변", result, action="warn")
        assert handled == "정확한 답변"

    @pytest.mark.asyncio
    async def test_hallucination_threshold(self):
        """설정된 threshold 적용 확인."""
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = (
            "grounded_ratio: 0.75\n"
            "ungrounded_claims: ['일부 주장']\n"
            "verdict: FAIL"
        )
        detector = HallucinationDetector(llm=mock_llm, threshold=0.7)
        result = await detector.verify(
            answer="테스트",
            documents=["문서"],
        )
        # grounded_ratio=0.75 > threshold=0.7 이므로 PASS로 재판정
        assert result.verdict == "PASS"

    @pytest.mark.asyncio
    async def test_verify_prompt_includes_documents(self):
        """verify 호출 시 문서 내용이 프롬프트에 포함되는지."""
        mock_llm = AsyncMock()
        mock_llm.generate.return_value = "grounded_ratio: 1.0\nungrounded_claims: []\nverdict: PASS"
        detector = HallucinationDetector(llm=mock_llm)
        await detector.verify(
            answer="답변",
            documents=["문서1 내용", "문서2 내용"],
        )
        call_args = mock_llm.generate.call_args
        prompt = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")
        assert "문서1 내용" in prompt
        assert "문서2 내용" in prompt
