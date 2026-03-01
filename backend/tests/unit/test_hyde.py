"""Step 4.6 RED: HyDE (Hypothetical Document Embeddings) 단위 테스트."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.services.hyde.generator import HyDEGenerator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_llm() -> AsyncMock:
    """LLMProvider 프로토콜을 만족하는 AsyncMock 생성."""
    llm = AsyncMock()
    llm.generate.return_value = (
        "한국의 독립운동은 1919년 3·1 운동을 계기로 본격화되었다. "
        "대한민국 임시정부가 상하이에 수립되어 독립운동을 이끌었으며, "
        "국내외에서 다양한 형태의 항일 운동이 전개되었다."
    )
    return llm


@pytest.fixture()
def hyde(mock_llm: AsyncMock) -> HyDEGenerator:
    """HyDEGenerator 인스턴스 생성."""
    return HyDEGenerator(llm=mock_llm)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hyde_generate(hyde: HyDEGenerator, mock_llm: AsyncMock):
    """Mock LLM을 통해 가상 문서가 정상적으로 생성되는지 검증."""
    query = "한국의 독립운동에 대해 설명해주세요"
    result = await hyde.generate(query)

    # LLM.generate가 한 번 호출되었는지 확인
    mock_llm.generate.assert_called_once()

    # 반환값이 LLM의 출력과 동일한지 확인
    assert result == mock_llm.generate.return_value
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_hyde_prompt_format(hyde: HyDEGenerator, mock_llm: AsyncMock):
    """LLM에 전달되는 프롬프트가 올바른 한국어 형식인지 검증."""
    query = "한국의 독립운동에 대해 설명해주세요"
    await hyde.generate(query)

    # LLM.generate에 전달된 프롬프트 추출
    call_args = mock_llm.generate.call_args
    prompt = call_args[0][0] if call_args[0] else call_args[1].get("prompt", "")

    # 프롬프트에 쿼리가 포함되어야 함
    assert query in prompt

    # 프롬프트에 지시문 키워드가 포함되어야 함
    assert "질문" in prompt
    assert "문서" in prompt


def test_hyde_should_apply_all(hyde: HyDEGenerator):
    """mode='all' → 항상 True를 반환해야 함."""
    assert hyde.should_apply("짧은 질문", mode="all") is True
    assert hyde.should_apply("", mode="all") is True
    assert hyde.should_apply("아주 긴 질문 " * 20, mode="all") is True


def test_hyde_should_apply_long_query(hyde: HyDEGenerator):
    """mode='long_query' → 쿼리 길이가 50자 초과일 때만 True."""
    long_query = "한국의 독립운동 역사에서 3·1 운동이 갖는 의미와 그 이후의 독립운동 전개 과정에 대해 자세히 설명해주세요"
    assert len(long_query) > 50  # 전제 조건 확인
    assert hyde.should_apply(long_query, mode="long_query") is True


def test_hyde_should_apply_short_query(hyde: HyDEGenerator):
    """mode='long_query' → 쿼리 길이가 50자 이하이면 False."""
    short_query = "한국 독립운동"
    assert len(short_query) <= 50  # 전제 조건 확인
    assert hyde.should_apply(short_query, mode="long_query") is False


def test_hyde_should_apply_complex(hyde: HyDEGenerator):
    """mode='complex' → 복합 질문(물음표 2개 이상 또는 접속사 포함)이면 True."""
    # 물음표 2개 이상
    multi_question = "한국의 독립운동은 언제 시작되었나요? 그리고 어떤 결과를 가져왔나요?"
    assert hyde.should_apply(multi_question, mode="complex") is True

    # 한국어 접속사 포함
    conjunction_query = "한국의 독립운동 뿐만 아니라 해외 독립운동에 대해서도 알려주세요"
    assert hyde.should_apply(conjunction_query, mode="complex") is True

    # "그리고" 접속사
    and_query = "3·1 운동 그리고 6·10 만세운동에 대해 알려주세요"
    assert hyde.should_apply(and_query, mode="complex") is True

    # "또한" 접속사
    also_query = "독립운동의 배경 또한 그 영향에 대해 설명해주세요"
    assert hyde.should_apply(also_query, mode="complex") is True

    # "하지만" 접속사
    but_query = "독립운동은 성공적이었다 하지만 많은 희생이 있었다"
    assert hyde.should_apply(but_query, mode="complex") is True

    # "및" 접속사
    and_marker_query = "국내 및 해외 독립운동의 차이점"
    assert hyde.should_apply(and_marker_query, mode="complex") is True

    # 전각 물음표 2개 이상
    fullwidth_question = "독립운동은 언제 시작되었나？ 그 결과는 어떠했나？"
    assert hyde.should_apply(fullwidth_question, mode="complex") is True

    # 단순 질문은 False
    simple_query = "한국 독립운동의 시작 시기"
    assert hyde.should_apply(simple_query, mode="complex") is False


def test_hyde_should_apply_unknown_mode(hyde: HyDEGenerator):
    """알 수 없는 mode가 주어지면 False를 반환해야 함."""
    assert hyde.should_apply("아무 질문", mode="unknown_mode") is False


def test_hyde_is_complex_korean_conjunctions(hyde: HyDEGenerator):
    """_is_complex 메서드가 한국어 접속사를 올바르게 감지하는지 검증."""
    # "와" 접속사 (조사로도 쓰이지만 복합 마커로 등록됨)
    assert hyde._is_complex("독립운동과 민주화운동") is True

    # "그런데" 접속사
    assert hyde._is_complex("독립운동은 성공했다 그런데 아직 과제가 남아있다") is True

    # 접속사 미포함 단순 문장
    assert hyde._is_complex("한국의 독립운동 역사") is False
