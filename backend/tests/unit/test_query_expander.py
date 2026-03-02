"""QueryExpander 단위 테스트: HyDE 기반 쿼리 확장."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.services.search.query_expander import QueryExpander


@pytest.fixture
def mock_llm():
    m = AsyncMock()
    return m


@pytest.fixture
def expander(mock_llm):
    return QueryExpander(llm=mock_llm)


class TestQueryExpander:

    @pytest.mark.asyncio
    async def test_expand_returns_expanded_query(self, expander, mock_llm):
        """확장 결과에 원본 쿼리와 키워드가 포함된 expanded_query가 반환되어야 한다."""
        mock_llm.generate.side_effect = [
            "자원봉사자의 활동 중 사회봉사명령은 인정 불가합니다.",  # HyDE 답변
            "자원봉사, 사회봉사명령, 인정 불가, 활동",  # 키워드 추출
        ]

        result = await expander.expand("자원봉사 인정 안 되는 경우는?")

        assert result.original_query == "자원봉사 인정 안 되는 경우는?"
        assert result.hypothetical_answer is not None
        assert len(result.expanded_keywords) > 0
        assert result.expanded_query is not None

    @pytest.mark.asyncio
    async def test_expand_preserves_original_query(self, expander, mock_llm):
        """expanded_query에 원본 쿼리가 포함되어야 한다."""
        mock_llm.generate.side_effect = [
            "SSH에서 Remote Control은 인바운드 포트를 사용합니다.",
            "SSH, Remote Control, 인바운드 포트",
        ]

        result = await expander.expand("Remote Control SSH 비교")

        assert "Remote Control SSH 비교" in result.expanded_query

    @pytest.mark.asyncio
    async def test_expand_respects_max_keywords(self, expander, mock_llm):
        """max_keywords를 초과하지 않아야 한다."""
        mock_llm.generate.side_effect = [
            "가상 답변 내용입니다.",
            "키워드1, 키워드2, 키워드3, 키워드4, 키워드5, 키워드6",
        ]

        result = await expander.expand("테스트 쿼리", max_keywords=3)

        assert len(result.expanded_keywords) <= 3

    @pytest.mark.asyncio
    async def test_expand_with_empty_keywords(self, expander, mock_llm):
        """LLM이 빈 키워드를 반환해도 원본 쿼리는 유지된다."""
        mock_llm.generate.side_effect = [
            "가상 답변입니다.",
            "",  # 빈 키워드
        ]

        result = await expander.expand("테스트 쿼리")

        assert result.expanded_query == "테스트 쿼리"
        assert result.expanded_keywords == []

    @pytest.mark.asyncio
    async def test_expand_llm_called_twice(self, expander, mock_llm):
        """LLM이 두 번 호출되어야 한다 (HyDE + 키워드 추출)."""
        mock_llm.generate.side_effect = [
            "가상 답변입니다.",
            "키워드1, 키워드2",
        ]

        await expander.expand("테스트 쿼리")

        assert mock_llm.generate.call_count == 2
