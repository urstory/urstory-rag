"""충실도 검증: 생성된 답변이 원문의 수치/빈도/용어를 왜곡하지 않았는지 확인."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.generation.base import LLMProvider

_FAITHFULNESS_PROMPT = """다음 검색된 문서와 생성된 답변을 비교하세요.
답변이 문서의 사실을 왜곡하거나 변형한 부분이 있는지 검증하세요.

검색된 문서:
{documents}

생성된 답변:
{answer}

특히 다음 항목을 집중 확인하세요:
1. 숫자/수치: 금액, 비율, 기간, 횟수가 원문과 정확히 일치하는가?
2. 주기/빈도: "반기별 1회"→"연 1회" 같은 변형이 없는가?
3. 고유명사/용어: 전문 용어가 정확한가?
4. 목록 완전성: 원문의 나열 항목이 빠짐없이 포함되어 있는가?

다음 형식으로 정확히 응답하세요:
faithfulness_score: 원문 충실도 점수 (0.0 ~ 1.0)
distortions: 왜곡된 항목 목록 (형식: "원문: X → 답변: Y")
verdict: FAITHFUL (score >= {threshold}) 또는 UNFAITHFUL"""


@dataclass
class FaithfulnessResult:
    faithfulness_score: float = 1.0
    distortions: list[str] = field(default_factory=list)
    verdict: str = "FAITHFUL"  # "FAITHFUL" or "UNFAITHFUL"


class FaithfulnessChecker:
    """LLM-as-Judge 충실도 검증기."""

    def __init__(
        self,
        llm: LLMProvider,
        threshold: float = 0.9,
    ) -> None:
        self.llm = llm
        self.threshold = threshold

    async def verify(
        self,
        answer: str,
        documents: list[str],
    ) -> FaithfulnessResult:
        """답변이 원문을 충실하게 반영하는지 검증."""
        docs_text = "\n---\n".join(documents)
        prompt = _FAITHFULNESS_PROMPT.format(
            documents=docs_text,
            answer=answer,
            threshold=self.threshold,
        )
        response = await self.llm.generate(prompt)
        result = self._parse_result(response)

        # threshold 적용하여 verdict 재판정
        if result.faithfulness_score >= self.threshold:
            result.verdict = "FAITHFUL"
        else:
            result.verdict = "UNFAITHFUL"

        return result

    @staticmethod
    def _parse_result(response: str) -> FaithfulnessResult:
        """LLM 응답을 파싱."""
        faithfulness_score = 1.0
        distortions: list[str] = []
        verdict = "FAITHFUL"

        for line in response.splitlines():
            line = line.strip()

            if line.lower().startswith("faithfulness_score"):
                match = re.search(r"[\d.]+", line.split(":", 1)[-1])
                if match:
                    faithfulness_score = float(match.group())

            elif line.lower().startswith("distortions"):
                claims_str = line.split(":", 1)[-1].strip()
                claims_str = claims_str.strip("[]")
                if claims_str and claims_str != "":
                    distortions = [
                        c.strip().strip("'\"")
                        for c in claims_str.split(",")
                        if c.strip().strip("'\"")
                    ]

            elif line.lower().startswith("verdict"):
                v = line.split(":", 1)[-1].strip().upper()
                if "UNFAITHFUL" in v:
                    verdict = "UNFAITHFUL"
                else:
                    verdict = "FAITHFUL"

        return FaithfulnessResult(
            faithfulness_score=faithfulness_score,
            distortions=distortions,
            verdict=verdict,
        )

    @staticmethod
    def handle_result(
        answer: str,
        result: FaithfulnessResult,
        action: str = "warn",
    ) -> str:
        """충실도 검증 결과에 따른 답변 처리.

        Args:
            answer: 원본 답변.
            result: 충실도 검증 결과.
            action: "warn" | "block".

        Returns:
            처리된 답변.
        """
        if result.verdict == "FAITHFUL":
            return answer

        if action == "block":
            return "답변의 정확성을 보장할 수 없습니다. 원문을 직접 확인해 주세요."

        if action == "warn":
            distortion_text = "; ".join(result.distortions) if result.distortions else ""
            warning = (
                f"\n\n⚠️ 이 답변에 원문과 다른 표현이 포함되어 있을 수 있습니다."
                f" (충실도: {result.faithfulness_score:.0%})"
            )
            if distortion_text:
                warning += f"\n주의 항목: {distortion_text}"
            return f"{answer}{warning}"

        return answer
