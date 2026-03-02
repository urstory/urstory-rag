"""룰 기반 질문 유형 분류기.

규정형(숫자/주기/횟수/금액) vs 설명형 질문을 분류한다.
LLM 호출 없이 정규식으로 동작하여 latency 추가 없음.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class QuestionType:
    category: str  # "regulatory" | "explanatory"
    confidence: float
    indicators: list[str] = field(default_factory=list)


class QuestionClassifier:
    """룰 기반 질문 유형 분류기.

    regulatory 패턴이 하나라도 매칭되면 regulatory로 분류.
    매칭되는 패턴이 없으면 explanatory로 분류.
    """

    REGULATORY_PATTERNS: list[tuple[str, str]] = [
        (r"\d+\s*[회번개점%원]", "숫자+단위"),
        (r"(몇|얼마나?)\s*(회|번|자주|많이)", "빈도 질문"),
        (r"(매|반기|분기|월|주|일)\s*(별|마다|단위)", "주기 표현"),
        (r"(기준|조건|요건|자격|한도|제한|상한|하한)", "기준/조건"),
        (r"(횟수|기간|주기|빈도|기한|유효)", "횟수/기간"),
        (r"(퍼센트|백분율|비율|점수)", "비율/점수"),
        (r"(금액|포인트|원|달러|만원|억원)", "금액"),
        (r"몇\s*(점|회|번|개|일|주|월|년)", "몇+단위"),
    ]

    def classify(self, query: str) -> QuestionType:
        """질문을 분류한다."""
        indicators = []

        for pattern, label in self.REGULATORY_PATTERNS:
            if re.search(pattern, query):
                indicators.append(label)

        if indicators:
            confidence = min(1.0, len(indicators) * 0.3)
            return QuestionType(
                category="regulatory",
                confidence=confidence,
                indicators=indicators,
            )

        return QuestionType(
            category="explanatory",
            confidence=0.5,
            indicators=[],
        )
