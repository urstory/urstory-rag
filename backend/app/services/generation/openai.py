"""Step 4.8 GREEN: OpenAI LLM 프로바이더."""
from __future__ import annotations

from openai import AsyncOpenAI

from app.exceptions import SearchServiceError


class OpenAILLM:
    """OpenAI API 기반 LLM 프로바이더.

    LLMProvider Protocol을 구현하며, AsyncOpenAI 클라이언트를 사용하여
    GPT 계열 모델로 텍스트를 생성한다.
    """

    # temperature를 지원하지 않는 모델 (기본값 1만 허용)
    _NO_TEMPERATURE_MODELS = {"gpt-5-mini", "gpt-5-nano"}

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4.1-mini",
        temperature: float = 0.3,
    ):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.temperature = temperature

    async def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        """OpenAI Chat Completions API로 텍스트를 생성한다.

        Args:
            prompt: 사용자 프롬프트
            system_prompt: 시스템 프롬프트 (선택)

        Returns:
            생성된 텍스트

        Raises:
            SearchServiceError: API 호출 실패 시
        """
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict = {"model": self.model, "messages": messages}
        if self.model not in self._NO_TEMPERATURE_MODELS:
            kwargs["temperature"] = self.temperature

        try:
            response = await self.client.chat.completions.create(**kwargs)
            return response.choices[0].message.content
        except Exception as e:
            raise SearchServiceError(
                f"OpenAI LLM generation failed: {e}"
            ) from e
