"""Step 4.8 GREEN: Claude (Anthropic) LLM 프로바이더."""
from __future__ import annotations

from anthropic import AsyncAnthropic

from app.exceptions import SearchServiceError


class ClaudeLLM:
    """Anthropic Claude API 기반 LLM 프로바이더.

    LLMProvider Protocol을 구현하며, AsyncAnthropic 클라이언트를 사용하여
    Claude 모델로 텍스트를 생성한다.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 2048,
    ):
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens

    async def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        """Anthropic Messages API로 텍스트를 생성한다.

        Args:
            prompt: 사용자 프롬프트
            system_prompt: 시스템 프롬프트 (선택)

        Returns:
            생성된 텍스트

        Raises:
            SearchServiceError: API 호출 실패 시
        """
        kwargs: dict = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        try:
            response = await self.client.messages.create(**kwargs)
            return response.content[0].text
        except Exception as e:
            raise SearchServiceError(
                f"Claude LLM generation failed: {e}"
            ) from e
