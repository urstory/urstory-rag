"""답변 내 숫자 검증 가드레일.

답변에 등장한 숫자/단위가 컨텍스트에도 존재하는지 룰 기반으로 검증한다.
LLM 호출 없이 정규식과 동등어 사전으로 동작.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class NumericVerification:
    passed: bool
    ungrounded_numbers: list[str] = field(default_factory=list)
    total_numbers_found: int = 0


class NumericVerifier:
    """답변 내 숫자/수치의 컨텍스트 존재 여부를 검증한다."""

    # 도메인 단위 화이트리스트 (오탐 방지)
    # 복합 단위(개월)를 단일 단위(개, 월)보다 앞에 배치하여 우선 매칭
    UNIT_PATTERN = r"(개월|반기|분기|회|번|개|점|%|원|시간|일|주|월|년|건|명|만|억|천)"
    # 주변 컨텍스트 포함: "연 1회", "반기별 1회" 등의 수식어+숫자+단위
    CONTEXT_PREFIX = r"(?:연|월|주|일|반기|분기|매)?\s*"
    NUMERIC_PATTERN = rf"(?<![제\w]){CONTEXT_PREFIX}\d+[\d,.]*\s*{UNIT_PATTERN}"

    # 동등어 사전: key 단위가 컨텍스트에 있으면 value 단위도 허용
    EQUIVALENTS: dict[str, list[str]] = {
        "반기": ["6개월", "반년"],
        "6개월": ["반기", "반년"],
        "분기": ["3개월"],
        "3개월": ["분기"],
        "연": ["1년", "12개월"],
        "1년": ["연", "12개월"],
        "12개월": ["연", "1년"],
        "월": ["30일"],
        "30일": ["월"],
    }

    def verify(
        self, answer: str, context_texts: list[str],
    ) -> NumericVerification:
        """답변의 수치가 컨텍스트에 근거하는지 검증한다."""
        answer_numbers = self._extract_numbers(answer)

        if not answer_numbers:
            return NumericVerification(passed=True, total_numbers_found=0)

        context_joined = " ".join(context_texts)
        context_normalized = self._normalize(context_joined)

        ungrounded = []
        for num_expr in answer_numbers:
            if not self._is_grounded(num_expr, context_normalized, context_joined):
                ungrounded.append(num_expr)

        return NumericVerification(
            passed=len(ungrounded) == 0,
            ungrounded_numbers=ungrounded,
            total_numbers_found=len(answer_numbers),
        )

    def _extract_numbers(self, text: str) -> list[str]:
        """텍스트에서 숫자+도메인 단위 표현을 추출한다."""
        matches = re.findall(self.NUMERIC_PATTERN, text)
        # findall은 그룹만 반환하므로 전체 매치를 다시 찾음
        full_matches = re.finditer(self.NUMERIC_PATTERN, text)
        return [m.group() for m in full_matches]

    def _is_grounded(
        self, num_expr: str, context_normalized: str, context_raw: str,
    ) -> bool:
        """숫자 표현이 컨텍스트에 근거하는지 확인한다."""
        normalized = self._normalize(num_expr)

        # 직접 매칭
        if normalized in context_normalized:
            return True

        # 원문 매칭 (쉼표 포함 등)
        if num_expr in context_raw:
            return True

        # 동등어 매칭
        for key, equivalents in self.EQUIVALENTS.items():
            if key in num_expr:
                for equiv in equivalents:
                    if equiv in context_raw or equiv in context_normalized:
                        return True

        return False

    @staticmethod
    def _normalize(text: str) -> str:
        """수치 표현 정규화: 쉼표/공백 제거."""
        return text.replace(",", "").replace(" ", "")
