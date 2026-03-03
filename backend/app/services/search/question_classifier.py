"""룰 기반 질문 유형 분류기.

extraction(고유명사/명칭/열거) vs regulatory(숫자/주기/횟수/금액) vs explanatory 분류.
LLM 호출 없이 정규식으로 동작하여 latency 추가 없음.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class QuestionType:
    category: str  # "extraction" | "regulatory" | "explanatory"
    confidence: float
    indicators: list[str] = field(default_factory=list)


class QuestionClassifier:
    """룰 기반 질문 유형 분류기.

    extraction 패턴 우선 체크 → regulatory 패턴 → explanatory 폴백.
    """

    EXTRACTION_PATTERNS: list[tuple[str, str]] = [
        (r"(이름|명칭|별칭)은?\s*(무엇|뭐|어떤)", "이름/명칭 질문"),
        (r"(기본\s*값|초기\s*값|디폴트)", "기본값 질문"),
        (r"(뭐|무엇)(이|을|를)?\s*(라고|이라고)\s*(부르|하|칭)", "명칭 질문"),
        (r"(세\s*가지|네\s*가지|다섯\s*가지|여섯\s*가지)", "열거 질문"),
        (r"내장된.+(이름|명칭|목록)", "내장 목록 질문"),
        (r"(어떤\s*(것들?|종류)|무엇무엇)", "열거 질문"),
    ]

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
        """질문을 분류한다. extraction > regulatory > explanatory 우선순위."""
        # 1. extraction 패턴 체크
        extraction_indicators = []
        for pattern, label in self.EXTRACTION_PATTERNS:
            if re.search(pattern, query):
                extraction_indicators.append(label)

        if extraction_indicators:
            return QuestionType(
                category="extraction",
                confidence=min(1.0, len(extraction_indicators) * 0.4),
                indicators=extraction_indicators,
            )

        # 2. regulatory 패턴 체크
        regulatory_indicators = []
        for pattern, label in self.REGULATORY_PATTERNS:
            if re.search(pattern, query):
                regulatory_indicators.append(label)

        if regulatory_indicators:
            return QuestionType(
                category="regulatory",
                confidence=min(1.0, len(regulatory_indicators) * 0.3),
                indicators=regulatory_indicators,
            )

        # 3. explanatory 폴백
        return QuestionType(
            category="explanatory",
            confidence=0.5,
            indicators=[],
        )
