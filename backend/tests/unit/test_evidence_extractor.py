"""EvidenceExtractor 단위 테스트: CoT 기반 근거 추출 + 답변 생성."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from app.models.schemas import SearchResult
from app.services.generation.evidence_extractor import EvidenceExtractor, EvidenceResult

DOC_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a1")


def _make_doc(content: str, score: float = 5.0) -> SearchResult:
    return SearchResult(
        chunk_id=uuid.uuid4(),
        document_id=DOC_ID,
        content=content,
        score=score,
    )


@pytest.fixture
def mock_llm():
    return AsyncMock()


@pytest.fixture
def extractor(mock_llm):
    return EvidenceExtractor(llm=mock_llm)


class TestEvidenceExtractor:

    @pytest.mark.asyncio
    async def test_extract_returns_evidence_sentences(self, extractor, mock_llm):
        """근거 문장이 1개 이상 추출된다."""
        mock_llm.generate.return_value = (
            "[근거]\n"
            "반기별 1회 이상 정기적으로 실시해야 합니다.\n\n"
            "[답변]\n"
            "평가는 반기별 1회 이상 정기적으로 실시해야 합니다."
        )
        docs = [_make_doc("반기별 1회 이상 정기적으로 실시해야 합니다.")]

        result = await extractor.extract_and_answer("평가 주기는?", docs)

        assert isinstance(result, EvidenceResult)
        assert len(result.evidence_sentences) >= 1

    @pytest.mark.asyncio
    async def test_answer_uses_evidence_numbers(self, extractor, mock_llm):
        """답변 내 숫자가 근거 문장에 포함된 수치와 동일하다."""
        mock_llm.generate.return_value = (
            "[근거]\n"
            "반기별 1회 이상 정기적으로 실시해야 합니다.\n\n"
            "[답변]\n"
            "반기별 1회 이상 정기적으로 실시해야 합니다."
        )
        docs = [_make_doc("반기별 1회 이상 정기적으로 실시해야 합니다.")]

        result = await extractor.extract_and_answer("평가 주기는?", docs)

        assert "반기별 1회" in result.answer

    @pytest.mark.asyncio
    async def test_no_evidence_returns_not_found(self, extractor, mock_llm):
        """근거를 찾을 수 없으면 '찾을 수 없습니다' 류 답변을 반환한다."""
        mock_llm.generate.return_value = (
            "[근거]\n"
            "근거 없음\n\n"
            "[답변]\n"
            "제공된 문서에서 관련 정보를 찾을 수 없습니다."
        )
        docs = [_make_doc("관련 없는 내용")]

        result = await extractor.extract_and_answer("전혀 다른 질문?", docs)

        assert "찾을 수 없" in result.answer or "근거 없음" in result.answer or len(result.evidence_sentences) == 0

    @pytest.mark.asyncio
    async def test_evidence_extraction_failure_falls_back(self, extractor, mock_llm):
        """LLM 호출 실패 시 None을 반환하여 기존 생성 프롬프트로 폴백 가능하게 한다."""
        mock_llm.generate.side_effect = Exception("LLM 호출 실패")
        docs = [_make_doc("테스트 문서")]

        result = await extractor.extract_and_answer("테스트 질문?", docs)

        assert result is None

    @pytest.mark.asyncio
    async def test_parse_response_separates_evidence_and_answer(self, extractor, mock_llm):
        """LLM 응답에서 [근거]와 [답변] 섹션이 올바르게 분리된다."""
        mock_llm.generate.return_value = (
            "[근거]\n"
            "첫 번째 근거 문장입니다.\n"
            "두 번째 근거 문장입니다.\n\n"
            "[답변]\n"
            "이것은 답변입니다."
        )
        docs = [_make_doc("테스트")]

        result = await extractor.extract_and_answer("질문?", docs)

        assert len(result.evidence_sentences) == 2
        assert result.answer == "이것은 답변입니다."

    @pytest.mark.asyncio
    async def test_single_llm_call_for_extract_and_answer(self, extractor, mock_llm):
        """CoT 통합으로 LLM이 정확히 1회만 호출된다."""
        mock_llm.generate.return_value = (
            "[근거]\n근거 문장\n\n[답변]\n답변 문장"
        )
        docs = [_make_doc("테스트")]

        await extractor.extract_and_answer("질문?", docs)

        assert mock_llm.generate.call_count == 1

    @pytest.mark.asyncio
    async def test_parse_response_without_sections_falls_back(self, extractor, mock_llm):
        """[근거]/[답변] 섹션 없이 응답하면 전체를 답변으로 처리한다."""
        mock_llm.generate.return_value = "단순한 답변만 반환합니다."
        docs = [_make_doc("테스트")]

        result = await extractor.extract_and_answer("질문?", docs)

        assert result.answer == "단순한 답변만 반환합니다."
        assert result.evidence_sentences == []


class TestExtractionMode:
    """추출 모드(extract_short_answer) 테스트."""

    @pytest.mark.asyncio
    async def test_extract_short_answer_returns_names(self, extractor, mock_llm):
        """고유명사 추출: 이름 목록을 정확히 반환한다."""
        mock_llm.generate.return_value = (
            "Task, Bash, File 에이전트\n\n"
            "[답변]\n"
            "1. Task\n2. Bash\n3. File"
        )
        docs = [_make_doc("내장 서브에이전트는 Task, Bash, File 세 가지입니다.")]

        result = await extractor.extract_short_answer(
            "내장된 서브에이전트의 이름은 무엇인가요?", docs,
        )

        assert result is not None
        assert "Task" in result.answer
        assert "Bash" in result.answer
        assert "File" in result.answer

    @pytest.mark.asyncio
    async def test_extract_short_answer_uses_extraction_prompt(self, extractor, mock_llm):
        """추출 모드는 EXTRACTION_SYSTEM_PROMPT를 사용한다."""
        mock_llm.generate.return_value = "[근거]\nfoo\n\n[답변]\nfoo"
        docs = [_make_doc("테스트")]

        await extractor.extract_short_answer("이름은 무엇?", docs)

        call_kwargs = mock_llm.generate.call_args
        assert "추출" in call_kwargs.kwargs.get("system_prompt", call_kwargs[1].get("system_prompt", ""))

    @pytest.mark.asyncio
    async def test_extract_short_answer_failure_returns_none(self, extractor, mock_llm):
        """LLM 호출 실패 시 None 반환."""
        mock_llm.generate.side_effect = Exception("실패")
        docs = [_make_doc("테스트")]

        result = await extractor.extract_short_answer("이름은?", docs)
        assert result is None
