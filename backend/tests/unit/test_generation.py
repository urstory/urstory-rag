"""Step 4.8 RED: 답변 생성 서비스 (OpenAI, Claude, 프롬프트) 단위 테스트."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.exceptions import SearchServiceError
from app.models.schemas import SearchResult
from app.services.generation.base import LLMProvider


# ---------------------------------------------------------------------------
# OpenAILLM 테스트
# ---------------------------------------------------------------------------


class TestOpenAILLM:
    """OpenAILLM 단위 테스트."""

    def test_openai_llm_protocol(self):
        """OpenAILLM이 LLMProvider Protocol을 구현하는지 확인."""
        from app.services.generation.openai import OpenAILLM

        llm = OpenAILLM(api_key="test-key")
        assert isinstance(llm, LLMProvider)

    async def test_openai_llm_generate(self):
        """Mock OpenAI 클라이언트로 텍스트 생성 검증."""
        from app.services.generation.openai import OpenAILLM

        llm = OpenAILLM(api_key="test-key", model="gpt-4")

        # Mock the response object chain: response.choices[0].message.content
        mock_message = MagicMock()
        mock_message.content = "OpenAI 답변입니다."
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        llm.client = AsyncMock()
        llm.client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await llm.generate("한국어 RAG란 무엇인가요?")

        assert result == "OpenAI 답변입니다."
        llm.client.chat.completions.create.assert_called_once()
        call_kwargs = llm.client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "gpt-4"
        # system prompt 없으므로 messages에 user만 있어야 함
        assert len(call_kwargs["messages"]) == 1
        assert call_kwargs["messages"][0]["role"] == "user"
        assert call_kwargs["messages"][0]["content"] == "한국어 RAG란 무엇인가요?"

    async def test_openai_llm_with_system_prompt(self):
        """시스템 프롬프트가 OpenAI messages에 올바르게 전달되는지 확인."""
        from app.services.generation.openai import OpenAILLM

        llm = OpenAILLM(api_key="test-key", model="gpt-4")

        mock_message = MagicMock()
        mock_message.content = "시스템 프롬프트 적용 답변"
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        llm.client = AsyncMock()
        llm.client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await llm.generate(
            "질문입니다",
            system_prompt="한국어로 답하세요",
        )

        assert result == "시스템 프롬프트 적용 답변"
        call_kwargs = llm.client.chat.completions.create.call_args.kwargs
        messages = call_kwargs["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "한국어로 답하세요"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "질문입니다"

    async def test_openai_llm_error(self):
        """OpenAI API 에러 발생 시 SearchServiceError로 래핑되는지 확인."""
        from app.services.generation.openai import OpenAILLM

        llm = OpenAILLM(api_key="test-key")

        llm.client = AsyncMock()
        llm.client.chat.completions.create = AsyncMock(
            side_effect=Exception("OpenAI API rate limit exceeded"),
        )

        with pytest.raises(SearchServiceError, match="OpenAI LLM"):
            await llm.generate("실패할 질문")


# ---------------------------------------------------------------------------
# ClaudeLLM 테스트
# ---------------------------------------------------------------------------


class TestClaudeLLM:
    """ClaudeLLM 단위 테스트."""

    def test_claude_llm_protocol(self):
        """ClaudeLLM이 LLMProvider Protocol을 구현하는지 확인."""
        from app.services.generation.claude import ClaudeLLM

        llm = ClaudeLLM(api_key="test-key")
        assert isinstance(llm, LLMProvider)

    async def test_claude_llm_generate(self):
        """Mock Anthropic 클라이언트로 텍스트 생성 검증."""
        from app.services.generation.claude import ClaudeLLM

        llm = ClaudeLLM(api_key="test-key", model="claude-sonnet-4-20250514")

        # Mock the response object chain: response.content[0].text
        mock_content_block = MagicMock()
        mock_content_block.text = "Claude 답변입니다."
        mock_response = MagicMock()
        mock_response.content = [mock_content_block]

        llm.client = AsyncMock()
        llm.client.messages.create = AsyncMock(return_value=mock_response)

        result = await llm.generate("한국어 RAG란 무엇인가요?")

        assert result == "Claude 답변입니다."
        llm.client.messages.create.assert_called_once()
        call_kwargs = llm.client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-sonnet-4-20250514"
        assert call_kwargs["messages"] == [{"role": "user", "content": "한국어 RAG란 무엇인가요?"}]
        # system prompt 없으므로 system 키가 없어야 함
        assert "system" not in call_kwargs

    async def test_claude_llm_with_system_prompt(self):
        """시스템 프롬프트가 Anthropic API의 system 파라미터로 전달되는지 확인."""
        from app.services.generation.claude import ClaudeLLM

        llm = ClaudeLLM(api_key="test-key", model="claude-sonnet-4-20250514")

        mock_content_block = MagicMock()
        mock_content_block.text = "시스템 프롬프트 적용 답변"
        mock_response = MagicMock()
        mock_response.content = [mock_content_block]

        llm.client = AsyncMock()
        llm.client.messages.create = AsyncMock(return_value=mock_response)

        result = await llm.generate(
            "질문입니다",
            system_prompt="한국어로 답하세요",
        )

        assert result == "시스템 프롬프트 적용 답변"
        call_kwargs = llm.client.messages.create.call_args.kwargs
        assert call_kwargs["system"] == "한국어로 답하세요"
        assert call_kwargs["messages"] == [{"role": "user", "content": "질문입니다"}]

    async def test_claude_llm_error(self):
        """Anthropic API 에러 발생 시 SearchServiceError로 래핑되는지 확인."""
        from app.services.generation.claude import ClaudeLLM

        llm = ClaudeLLM(api_key="test-key")

        llm.client = AsyncMock()
        llm.client.messages.create = AsyncMock(
            side_effect=Exception("Anthropic API error"),
        )

        with pytest.raises(SearchServiceError, match="Claude LLM"):
            await llm.generate("실패할 질문")


# ---------------------------------------------------------------------------
# Prompt Builder 테스트
# ---------------------------------------------------------------------------


class TestPromptBuilder:
    """프롬프트 빌더 단위 테스트."""

    def _make_search_result(
        self,
        content: str = "테스트 문서 내용",
        score: float = 0.9,
    ) -> SearchResult:
        """테스트용 SearchResult 객체 생성."""
        return SearchResult(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            content=content,
            score=score,
        )

    def test_prompt_builder_format(self):
        """documents + query로 포맷된 프롬프트가 올바르게 생성되는지 확인."""
        from app.services.generation.prompts import build_prompt

        docs = [
            self._make_search_result(content="RAG는 검색 증강 생성입니다."),
            self._make_search_result(content="한국어 NLP 처리가 필요합니다."),
        ]

        result = build_prompt(query="RAG란 무엇인가요?", documents=docs)

        # 각 문서가 번호와 함께 포함되어야 함
        assert "[문서 1]" in result
        assert "RAG는 검색 증강 생성입니다." in result
        assert "[문서 2]" in result
        assert "한국어 NLP 처리가 필요합니다." in result
        # 문서 사이 구분자 확인
        assert "---" in result
        # 질문이 포함되어야 함
        assert "RAG란 무엇인가요?" in result
        # 답변 유도 접미사
        assert "답변:" in result

    def test_prompt_builder_system_prompt(self):
        """시스템 프롬프트 내용이 올바른지 확인."""
        from app.services.generation.prompts import SYSTEM_PROMPT

        # 핵심 규칙이 시스템 프롬프트에 포함되어 있는지 확인
        assert "문서" in SYSTEM_PROMPT
        assert "답변" in SYSTEM_PROMPT
        # 출처 명시 규칙
        assert "출처" in SYSTEM_PROMPT
        # 문서에 없는 내용에 대한 처리 규칙
        assert "찾을 수 없습니다" in SYSTEM_PROMPT
        # 개인정보 마스킹 규칙
        assert "개인정보" in SYSTEM_PROMPT

    def test_prompt_builder_empty_docs(self):
        """문서가 없을 때 적절한 메시지가 포함되는지 확인."""
        from app.services.generation.prompts import build_prompt

        result = build_prompt(query="질문입니다", documents=[])

        assert "검색된 문서가 없습니다" in result
        assert "질문입니다" in result
        # 문서 번호 표기가 없어야 함
        assert "[문서 1]" not in result

    def test_prompt_builder_single_doc(self):
        """단일 문서로 프롬프트가 올바르게 생성되는지 확인."""
        from app.services.generation.prompts import build_prompt

        docs = [self._make_search_result(content="단일 문서 내용입니다.")]

        result = build_prompt(query="질문", documents=docs)

        assert "[문서 1]" in result
        assert "단일 문서 내용입니다." in result
        # 구분자가 없어야 함 (문서가 1개이므로)
        assert result.count("---") <= 1  # 구분자가 문서 사이에만 존재
