"""Step 5.1-5.2: 한국어 PII 탐지 단위 테스트."""
import pytest

from app.services.guardrails.pii import KoreanPIIDetector, PIIMatch


class TestRegexScan:
    """Step 5.1: 정규식 기반 PII 탐지."""

    def setup_method(self):
        self.detector = KoreanPIIDetector()

    def test_detect_resident_number(self):
        """주민등록번호 탐지."""
        text = "주민번호는 880101-1234567 입니다"
        matches = self.detector.regex_scan(text)
        assert len(matches) == 1
        assert matches[0].pii_type == "주민등록번호"
        assert matches[0].value == "880101-1234567"

    def test_detect_resident_number_female(self):
        """여성 주민등록번호 탐지."""
        text = "950315-2345678"
        matches = self.detector.regex_scan(text)
        assert len(matches) == 1
        assert matches[0].pii_type == "주민등록번호"

    def test_detect_foreign_resident_number(self):
        """외국인등록번호 탐지."""
        text = "외국인등록번호: 880101-5234567"
        matches = self.detector.regex_scan(text)
        assert len(matches) == 1
        assert matches[0].pii_type == "외국인등록번호"

    def test_detect_phone_number(self):
        """휴대전화번호 탐지."""
        text = "연락처: 010-1234-5678"
        matches = self.detector.regex_scan(text)
        assert len(matches) == 1
        assert matches[0].pii_type == "휴대전화"
        assert matches[0].value == "010-1234-5678"

    def test_detect_phone_number_no_dash(self):
        """대시 없는 휴대전화번호."""
        text = "전화 01012345678"
        matches = self.detector.regex_scan(text)
        assert len(matches) == 1
        assert matches[0].pii_type == "휴대전화"

    def test_detect_landline(self):
        """일반전화번호 탐지."""
        text = "사무실: 02-1234-5678"
        matches = self.detector.regex_scan(text)
        assert len(matches) == 1
        assert matches[0].pii_type == "일반전화"

    def test_detect_business_number(self):
        """사업자등록번호 탐지."""
        text = "사업자번호 123-45-67890"
        matches = self.detector.regex_scan(text)
        assert len(matches) == 1
        assert matches[0].pii_type == "사업자등록번호"
        assert matches[0].value == "123-45-67890"

    def test_detect_passport(self):
        """여권번호 탐지."""
        text = "여권번호: M12345678"
        matches = self.detector.regex_scan(text)
        assert len(matches) == 1
        assert matches[0].pii_type == "여권번호"

    def test_detect_driver_license(self):
        """운전면허번호 탐지."""
        text = "면허번호 11-22-333333-44"
        matches = self.detector.regex_scan(text)
        assert len(matches) == 1
        assert matches[0].pii_type == "운전면허번호"

    def test_detect_email(self):
        """이메일 탐지."""
        text = "이메일: user@example.com"
        matches = self.detector.regex_scan(text)
        assert len(matches) == 1
        assert matches[0].pii_type == "이메일"
        assert matches[0].value == "user@example.com"

    def test_detect_account_number(self):
        """계좌번호 탐지."""
        text = "계좌: 110-234-567890"
        matches = self.detector.regex_scan(text)
        assert len(matches) == 1
        assert matches[0].pii_type == "계좌번호"

    def test_no_false_positive_date(self):
        """날짜를 PII로 오탐하지 않아야 함."""
        text = "2026-03-01 회의가 있습니다"
        matches = self.detector.regex_scan(text)
        pii_types = [m.pii_type for m in matches]
        assert "주민등록번호" not in pii_types
        assert "외국인등록번호" not in pii_types

    def test_no_false_positive_plain_number(self):
        """일반 숫자를 오탐하지 않아야 함."""
        text = "총 금액은 123456원입니다"
        matches = self.detector.regex_scan(text)
        assert len(matches) == 0

    def test_multiple_pii_in_text(self):
        """한 텍스트에서 여러 PII 동시 탐지."""
        text = "이름: 홍길동, 주민번호: 880101-1234567, 연락처: 010-9876-5432, 이메일: hong@test.com"
        matches = self.detector.regex_scan(text)
        types = {m.pii_type for m in matches}
        assert "주민등록번호" in types
        assert "휴대전화" in types
        assert "이메일" in types

    def test_pii_match_positions(self):
        """PIIMatch의 start/end 위치 정확성."""
        text = "번호: 010-1234-5678 입니다"
        matches = self.detector.regex_scan(text)
        assert len(matches) == 1
        m = matches[0]
        assert text[m.start:m.end] == "010-1234-5678"


class TestMasking:
    """Step 5.2: PII 마스킹."""

    def setup_method(self):
        self.detector = KoreanPIIDetector()

    def test_mask_phone(self):
        """전화번호 마스킹: 010-****-****."""
        match = PIIMatch(pii_type="휴대전화", value="010-1234-5678", start=0, end=13)
        masked = self.detector.mask_value(match)
        assert masked == "010-****-****"

    def test_mask_resident_number(self):
        """주민번호 마스킹: 880101-*******."""
        match = PIIMatch(pii_type="주민등록번호", value="880101-1234567", start=0, end=14)
        masked = self.detector.mask_value(match)
        assert masked == "880101-*******"

    def test_mask_email(self):
        """이메일 마스킹: u***@example.com."""
        match = PIIMatch(pii_type="이메일", value="user@example.com", start=0, end=16)
        masked = self.detector.mask_value(match)
        assert "***" in masked
        assert "@" in masked

    def test_mask_business_number(self):
        """사업자번호 마스킹: 123-**-*****."""
        match = PIIMatch(pii_type="사업자등록번호", value="123-45-67890", start=0, end=12)
        masked = self.detector.mask_value(match)
        assert masked == "123-**-*****"

    def test_mask_text(self):
        """전체 텍스트에서 PII 마스킹."""
        text = "연락처: 010-1234-5678"
        matches = [PIIMatch(pii_type="휴대전화", value="010-1234-5678", start=5, end=18)]
        result = self.detector.mask(text, matches)
        assert "1234" not in result
        assert "010-****-****" in result

    def test_mask_multiple(self):
        """여러 PII 동시 마스킹."""
        text = "주민: 880101-1234567, 폰: 010-9876-5432"
        matches = [
            PIIMatch(pii_type="주민등록번호", value="880101-1234567", start=4, end=18),
            PIIMatch(pii_type="휴대전화", value="010-9876-5432", start=24, end=37),
        ]
        result = self.detector.mask(text, matches)
        assert "1234567" not in result
        assert "9876" not in result


class TestDetectAsync:
    """Step 5.2: 비동기 detect (LLM 검증 포함)."""

    @pytest.mark.asyncio
    async def test_detect_no_pii(self):
        """PII 없는 텍스트 → 빈 리스트."""
        detector = KoreanPIIDetector()
        matches = await detector.detect("오늘 날씨가 좋습니다")
        assert matches == []

    @pytest.mark.asyncio
    async def test_detect_with_pii_no_llm(self):
        """LLM 검증 OFF → 정규식 결과만 반환."""
        detector = KoreanPIIDetector(llm=None)
        matches = await detector.detect("전화: 010-1234-5678")
        assert len(matches) == 1
        assert matches[0].pii_type == "휴대전화"
