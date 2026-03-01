"""LLM-as-Judge 할루시네이션 탐지.

코사인 유사도 사용 금지 — LLM 기반 사실 검증만 사용.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.generation.base import LLMProvider

_JUDGE_PROMPT = """다음 검색된 문서와 생성된 답변을 비교하세요.
답변의 각 주장이 검색된 문서에 근거하고 있는지 판단하세요.

검색된 문서:
{documents}

생성된 답변:
{answer}

다음 형식으로 정확히 응답하세요:
grounded_ratio: 문서에서 직접 확인되는 주장의 비율 (0.0 ~ 1.0)
ungrounded_claims: 문서에서 확인할 수 없는 주장 목록
verdict: PASS (grounded_ratio >= {threshold}) 또는 FAIL"""


@dataclass
class HallucinationResult:
    grounded_ratio: float = 1.0
    ungrounded_claims: list[str] = field(default_factory=list)
    verdict: str = "PASS"  # "PASS" or "FAIL"


class HallucinationDetector:
    """LLM-as-Judge 할루시네이션 탐지기."""

    def __init__(
        self,
        llm: LLMProvider,
        threshold: float = 0.8,
    ) -> None:
        self.llm = llm
        self.threshold = threshold

    async def verify(
        self,
        answer: str,
        documents: list[str],
    ) -> HallucinationResult:
        """답변이 문서에 근거하는지 검증."""
        docs_text = "\n---\n".join(documents)
        prompt = _JUDGE_PROMPT.format(
            documents=docs_text,
            answer=answer,
            threshold=self.threshold,
        )
        response = await self.llm.generate(prompt)
        result = self._parse_result(response)

        # threshold를 적용하여 verdict 재판정
        if result.grounded_ratio >= self.threshold:
            result.verdict = "PASS"
        else:
            result.verdict = "FAIL"

        return result

    @staticmethod
    def _parse_result(response: str) -> HallucinationResult:
        """LLM 응답을 파싱."""
        grounded_ratio = 1.0
        ungrounded_claims: list[str] = []
        verdict = "PASS"

        for line in response.splitlines():
            line = line.strip()

            # grounded_ratio 파싱
            if line.lower().startswith("grounded_ratio"):
                match = re.search(r"[\d.]+", line.split(":", 1)[-1])
                if match:
                    grounded_ratio = float(match.group())

            # ungrounded_claims 파싱
            elif line.lower().startswith("ungrounded_claims"):
                claims_str = line.split(":", 1)[-1].strip()
                # ['claim1', 'claim2'] 형태 파싱
                claims_str = claims_str.strip("[]")
                if claims_str and claims_str != "":
                    ungrounded_claims = [
                        c.strip().strip("'\"")
                        for c in claims_str.split(",")
                        if c.strip().strip("'\"")
                    ]

            # verdict 파싱
            elif line.lower().startswith("verdict"):
                v = line.split(":", 1)[-1].strip().upper()
                if "FAIL" in v:
                    verdict = "FAIL"
                else:
                    verdict = "PASS"

        return HallucinationResult(
            grounded_ratio=grounded_ratio,
            ungrounded_claims=ungrounded_claims,
            verdict=verdict,
        )

    @staticmethod
    def handle_result(
        answer: str,
        result: HallucinationResult,
        action: str = "warn",
    ) -> str:
        """할루시네이션 결과에 따른 답변 처리.

        Args:
            answer: 원본 답변.
            result: 할루시네이션 검증 결과.
            action: "warn" | "block" | "regenerate".

        Returns:
            처리된 답변.
        """
        if result.verdict == "PASS":
            return answer

        if action == "block":
            return "답변을 생성할 수 없습니다. 제공된 문서에서 충분한 근거를 찾지 못했습니다."

        if action == "warn":
            return (
                f"{answer}\n\n"
                "⚠️ 이 답변의 일부는 제공된 문서에서 확인되지 않았습니다. "
                f"(근거 비율: {result.grounded_ratio:.0%})"
            )

        # regenerate — 호출자가 재생성 처리해야 함
        return answer
