"""한국어 PII 탐지 + LLM 2차 검증 + 마스킹."""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.generation.base import LLMProvider


@dataclass
class PIIMatch:
    pii_type: str
    value: str
    start: int
    end: int


# 패턴 (우선순위 순서: 높은 것이 먼저 — 겹치면 우선순위 높은 것 유지)
_ORDERED_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("주민등록번호", re.compile(r"(?<!\d)\d{6}-[1-4]\d{6}(?!\d)")),
    ("외국인등록번호", re.compile(r"(?<!\d)\d{6}-[5-8]\d{6}(?!\d)")),
    ("운전면허번호", re.compile(r"(?<!\d)\d{2}-\d{2}-\d{6}-\d{2}(?!\d)")),
    ("휴대전화", re.compile(r"01[016-9]-?\d{3,4}-?\d{4}(?!\d)")),
    ("사업자등록번호", re.compile(r"(?<!\d)\d{3}-\d{2}-\d{5}(?!\d)")),
    ("일반전화", re.compile(r"(?<!\d)0\d{1,2}-\d{3,4}-\d{4}(?!\d)")),
    ("여권번호", re.compile(r"(?<![A-Z])[A-Z]\d{8}(?!\d)")),
    ("이메일", re.compile(r"[\w.-]+@[\w.-]+\.\w+")),
    ("계좌번호", re.compile(r"(?<!\d)\d{3,4}-\d{2,6}-\d{2,6}(?!\d)")),
]

# 날짜 패턴 (오탐 제거용)
_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")


class KoreanPIIDetector:
    """한국어 PII 탐지기.

    1차 정규식 스캔 → (선택적) 2차 LLM 검증 → 마스킹.
    """

    def __init__(self, llm: LLMProvider | None = None) -> None:
        self.llm = llm

    def regex_scan(self, text: str) -> list[PIIMatch]:
        """1차: 정규식 기반 PII 후보 추출."""
        # 날짜 위치를 먼저 수집 (오탐 방지)
        date_ranges = set()
        for m in _DATE_PATTERN.finditer(text):
            for i in range(m.start(), m.end()):
                date_ranges.add(i)

        # 이미 점유된 텍스트 범위 (우선순위 높은 패턴이 먼저 차지)
        occupied: set[int] = set()
        candidates: list[PIIMatch] = []

        for pii_type, pattern in _ORDERED_PATTERNS:
            for m in pattern.finditer(text):
                span = range(m.start(), m.end())
                # 날짜 범위와 겹치면 건너뛴다
                if pii_type in ("주민등록번호", "외국인등록번호", "계좌번호"):
                    if any(i in date_ranges for i in span):
                        continue
                # 우선순위 높은 패턴이 이미 차지한 범위와 겹치면 건너뛴다
                if any(i in occupied for i in span):
                    continue
                occupied.update(span)
                candidates.append(PIIMatch(
                    pii_type=pii_type,
                    value=m.group(),
                    start=m.start(),
                    end=m.end(),
                ))
        return candidates

    async def detect(
        self,
        text: str,
        llm_verification: bool = True,
    ) -> list[PIIMatch]:
        """PII 탐지 (정규식 + 선택적 LLM 검증).

        Args:
            text: 검사할 텍스트.
            llm_verification: True이고 self.llm이 설정되어 있으면 LLM 2차 검증.

        Returns:
            확인된 PIIMatch 리스트.
        """
        candidates = self.regex_scan(text)
        if not candidates:
            return []

        if llm_verification and self.llm is not None:
            return await self._llm_verify(text, candidates)

        return candidates

    async def _llm_verify(
        self, text: str, candidates: list[PIIMatch],
    ) -> list[PIIMatch]:
        """2차: LLM으로 오탐 제거."""
        items = "\n".join(
            f"- [{m.pii_type}] \"{m.value}\"" for m in candidates
        )
        prompt = (
            "다음 텍스트에서 탐지된 항목이 실제 개인정보인지 판단하세요.\n\n"
            f"텍스트: {text}\n\n"
            f"탐지된 항목:\n{items}\n\n"
            "각 항목에 대해 한 줄씩 '실제' 또는 '오탐'으로만 응답하세요."
        )
        result = await self.llm.generate(prompt)
        return self._parse_verified(candidates, result)

    @staticmethod
    def _parse_verified(
        candidates: list[PIIMatch], llm_response: str,
    ) -> list[PIIMatch]:
        """LLM 응답을 파싱하여 실제 PII만 필터링."""
        lines = [ln.strip() for ln in llm_response.strip().splitlines() if ln.strip()]
        verified: list[PIIMatch] = []
        for i, candidate in enumerate(candidates):
            if i < len(lines):
                if "오탐" in lines[i]:
                    continue
            # LLM 응답이 부족하면 안전하게 PII로 간주
            verified.append(candidate)
        return verified

    def mask_value(self, match: PIIMatch) -> str:
        """개별 PII 값 마스킹."""
        v = match.value
        t = match.pii_type

        if t == "주민등록번호" or t == "외국인등록번호":
            # 880101-1234567 → 880101-*******
            parts = v.split("-")
            if len(parts) == 2:
                return f"{parts[0]}-{'*' * len(parts[1])}"

        if t == "휴대전화":
            # 010-1234-5678 → 010-****-****
            if "-" in v:
                parts = v.split("-")
                return f"{parts[0]}-{'*' * len(parts[1])}-{'*' * len(parts[2])}"
            # 01012345678 → 010****5678 → 간단하게 뒤 8자리 마스킹
            return v[:3] + "*" * (len(v) - 3)

        if t == "일반전화":
            parts = v.split("-")
            if len(parts) == 3:
                return f"{parts[0]}-{'*' * len(parts[1])}-{'*' * len(parts[2])}"

        if t == "사업자등록번호":
            # 123-45-67890 → 123-**-*****
            parts = v.split("-")
            if len(parts) == 3:
                return f"{parts[0]}-{'*' * len(parts[1])}-{'*' * len(parts[2])}"

        if t == "이메일":
            # user@example.com → u***@example.com
            local, domain = v.split("@", 1)
            if len(local) <= 1:
                masked_local = local + "***"
            else:
                masked_local = local[0] + "***"
            return f"{masked_local}@{domain}"

        if t == "여권번호":
            # M12345678 → M********
            return v[0] + "*" * (len(v) - 1)

        if t == "운전면허번호":
            # 11-22-333333-44 → 11-**-******-**
            parts = v.split("-")
            if len(parts) == 4:
                return f"{parts[0]}-{'*' * len(parts[1])}-{'*' * len(parts[2])}-{'*' * len(parts[3])}"

        if t == "계좌번호":
            parts = v.split("-")
            if len(parts) >= 2:
                return parts[0] + "-" + "-".join("*" * len(p) for p in parts[1:])

        # 기본: 앞 2글자 유지, 나머지 마스킹
        return v[:2] + "*" * (len(v) - 2)

    def mask(self, text: str, matches: list[PIIMatch]) -> str:
        """텍스트에서 모든 탐지된 PII를 마스킹."""
        # 뒤에서부터 치환 (위치가 밀리지 않도록)
        for m in sorted(matches, key=lambda x: x.start, reverse=True):
            masked = self.mask_value(m)
            text = text[:m.start] + masked + text[m.end:]
        return text
