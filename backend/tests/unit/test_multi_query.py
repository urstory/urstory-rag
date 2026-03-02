"""MultiQueryGenerator 단위 테스트: LLM 기반 멀티쿼리 생성."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.services.search.multi_query import MultiQueryGenerator, MultiQueryResult


@pytest.fixture
def mock_llm():
    return AsyncMock()


@pytest.fixture
def generator(mock_llm):
    return MultiQueryGenerator(llm=mock_llm)


class TestMultiQueryGenerator:

    @pytest.mark.asyncio
    async def test_generate_returns_original_plus_variants(self, generator, mock_llm):
        """원문 + 변형 쿼리가 count 이하로 반환된다."""
        mock_llm.generate.return_value = (
            "봉사활동 인정 기준은 무엇인가요?\n"
            "자원봉사 인정 불가 사례에는 어떤 것이 있나요?\n"
            "인정되는 봉사활동의 종류와 조건"
        )

        result = await generator.generate("인정되지 않는 봉사 형태는?", count=4)

        assert isinstance(result, MultiQueryResult)
        assert len(result.variant_queries) <= 4
        assert len(result.variant_queries) >= 1

    @pytest.mark.asyncio
    async def test_generate_includes_original_query(self, generator, mock_llm):
        """결과에 원문 쿼리가 항상 포함된다."""
        mock_llm.generate.return_value = "변형 질문1\n변형 질문2\n변형 질문3"

        result = await generator.generate("원문 질문입니다", count=4)

        assert result.original_query == "원문 질문입니다"
        assert "원문 질문입니다" in result.variant_queries

    @pytest.mark.asyncio
    async def test_comparison_query_splits_into_subqueries(self, generator, mock_llm):
        """비교 질문이 각 대상별 개별 질문으로 분리된다."""
        mock_llm.generate.return_value = (
            "장기요양 1등급 인정 기준은?\n"
            "장기요양 2등급 인정 기준은?\n"
            "장기요양 등급 판정 기준"
        )

        result = await generator.generate("장기요양 1등급과 2등급의 차이는?", count=4)

        assert len(result.variant_queries) > 1
        # 프롬프트에 비교 분리 규칙이 반영됨
        prompt_used = mock_llm.generate.call_args[0][0]
        assert "비교" in prompt_used
        assert "개별 질문" in prompt_used

    @pytest.mark.asyncio
    async def test_complex_query_splits_conditions(self, generator, mock_llm):
        """복합 조건 질문이 조건별로 분리된다."""
        mock_llm.generate.return_value = (
            "봉사활동 인정 기준은?\n"
            "봉사활동 인정 불가 사례는?\n"
            "봉사활동 인정 절차"
        )

        result = await generator.generate(
            "인정되는 봉사 형태와 인정되지 않는 봉사 형태는?", count=4
        )

        assert len(result.variant_queries) > 1
        prompt_used = mock_llm.generate.call_args[0][0]
        assert "복합 질문" in prompt_used

    @pytest.mark.asyncio
    async def test_parse_variants_handles_numbered_lines(self, generator, mock_llm):
        """LLM이 번호를 붙여도 정상 파싱한다."""
        mock_llm.generate.return_value = (
            "1. 봉사활동 인정 기준은?\n"
            "2. 인정되는 봉사 형태와 조건\n"
            "3. 봉사활동 제외 대상"
        )

        result = await generator.generate("인정되지 않는 봉사 형태는?", count=4)

        for q in result.variant_queries:
            if q != "인정되지 않는 봉사 형태는?":
                assert not q.startswith("1.")
                assert not q.startswith("2.")
                assert not q.startswith("3.")

    @pytest.mark.asyncio
    async def test_parse_variants_handles_empty_response(self, generator, mock_llm):
        """LLM 응답이 비어있으면 원문만 반환한다."""
        mock_llm.generate.return_value = ""

        result = await generator.generate("테스트 질문")

        assert result.variant_queries == ["테스트 질문"]

    @pytest.mark.asyncio
    async def test_llm_failure_returns_original_only(self, generator, mock_llm):
        """LLM 호출 실패 시 원문만으로 폴백한다."""
        mock_llm.generate.side_effect = Exception("LLM 호출 실패")

        result = await generator.generate("테스트 질문")

        assert result.variant_queries == ["테스트 질문"]
        assert result.original_query == "테스트 질문"
