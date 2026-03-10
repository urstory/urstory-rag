"""OpenAI LLM 프로바이더 (재시도 + Circuit Breaker)."""
from __future__ import annotations

import asyncio
import logging
import random

from openai import APIError, APIStatusError, AsyncOpenAI, RateLimitError

from app.exceptions import CircuitBreakerOpenError, SearchServiceError
from app.services.resilience import CircuitBreaker

logger = logging.getLogger(__name__)

# 재시도 대상: Rate Limit(429), 서버 에러(5xx)
_RETRYABLE_OPENAI = (RateLimitError, APIError)

# 재시도 대상 HTTP 상태 코드
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 529}


def _is_retryable(e: Exception) -> bool:
    """재시도 가능한 예외인지 판단."""
    if isinstance(e, RateLimitError):
        return True
    if isinstance(e, APIStatusError):
        return e.status_code in _RETRYABLE_STATUS_CODES
    if isinstance(e, APIError):
        return True
    return False


class OpenAILLM:
    """OpenAI API 기반 LLM 프로바이더 (재시도 + Circuit Breaker)."""

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
        self._circuit_breaker = CircuitBreaker(
            name="openai-llm",
            failure_threshold=5,
            recovery_timeout=30.0,
        )

    async def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        """OpenAI Chat Completions API로 텍스트를 생성한다.

        재시도: 최대 3회 (429, 500, 503 에러 시)
        Circuit Breaker: 연속 5회 실패 시 30초 동안 회로 열림
        """
        # Circuit Breaker 사전 확인
        if not self._circuit_breaker.allow_request():
            raise CircuitBreakerOpenError(
                f"Circuit Breaker [{self._circuit_breaker.name}] OPEN — "
                f"LLM 서비스 일시 중단"
            )

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs: dict = {"model": self.model, "messages": messages}
        if self.model not in self._NO_TEMPERATURE_MODELS:
            kwargs["temperature"] = self.temperature

        last_error: Exception | None = None
        max_retries = 3

        for attempt in range(max_retries + 1):
            try:
                response = await self.client.chat.completions.create(**kwargs)
                self._circuit_breaker.record_success()
                return response.choices[0].message.content
            except Exception as e:
                if _is_retryable(e) and attempt < max_retries:
                    last_error = e
                    delay = min(1.0 * (2 ** attempt), 30.0)
                    jitter = delay * random.uniform(0.5, 1.0)
                    logger.warning(
                        "LLM 재시도 %d/%d — %s (%.1f초 후)",
                        attempt + 1, max_retries, str(e)[:100], jitter,
                    )
                    await asyncio.sleep(jitter)
                elif _is_retryable(e):
                    last_error = e
                    self._circuit_breaker.record_failure()
                else:
                    self._circuit_breaker.record_failure()
                    raise SearchServiceError(
                        f"OpenAI LLM generation failed: {e}"
                    ) from e

        raise SearchServiceError(
            f"OpenAI LLM generation failed after {max_retries} retries: {last_error}"
        ) from last_error
