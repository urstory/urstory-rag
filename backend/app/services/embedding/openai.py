"""OpenAI 임베딩 프로바이더 (재시도 + Circuit Breaker)."""
import logging

import tiktoken
from openai import APIError, AsyncOpenAI, RateLimitError

from app.exceptions import CircuitBreakerOpenError, EmbeddingServiceError
from app.services.resilience import CircuitBreaker, with_retry

logger = logging.getLogger(__name__)

# 재시도 대상: Rate Limit(429), 서버 에러(500/503)
_RETRYABLE_OPENAI = (RateLimitError, APIError)


class OpenAIEmbedding:
    MAX_TOKENS = 8191  # text-embedding-3-small/large 최대 토큰

    def __init__(self, api_key: str, model: str = "text-embedding-3-small", dimensions: int | None = None):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.dimensions = dimensions
        self._circuit_breaker = CircuitBreaker(
            name="openai-embedding",
            failure_threshold=5,
            recovery_timeout=30.0,
        )
        try:
            self._enc = tiktoken.encoding_for_model(model)
        except KeyError:
            self._enc = tiktoken.get_encoding("cl100k_base")

    def _truncate(self, text: str) -> str:
        """토큰 수가 MAX_TOKENS를 초과하면 잘라냄."""
        tokens = self._enc.encode(text)
        if len(tokens) <= self.MAX_TOKENS:
            return text
        return self._enc.decode(tokens[:self.MAX_TOKENS])

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self._embed_with_retry(texts)

    async def embed_query(self, text: str) -> list[float]:
        results = await self.embed_documents([text])
        return results[0]

    async def _embed_with_retry(self, texts: list[str]) -> list[list[float]]:
        # Circuit Breaker 사전 확인
        if not self._circuit_breaker.allow_request():
            raise CircuitBreakerOpenError(
                f"Circuit Breaker [{self._circuit_breaker.name}] OPEN — "
                f"임베딩 서비스 일시 중단"
            )

        truncated = [self._truncate(t) for t in texts]
        kwargs: dict = {"model": self.model, "input": truncated}
        if self.dimensions:
            kwargs["dimensions"] = self.dimensions

        last_error: Exception | None = None
        max_retries = 3

        for attempt in range(max_retries + 1):
            try:
                response = await self.client.embeddings.create(**kwargs)
                self._circuit_breaker.record_success()
                return [item.embedding for item in response.data]
            except _RETRYABLE_OPENAI as e:
                last_error = e
                if attempt < max_retries:
                    import asyncio
                    import random
                    delay = min(1.0 * (2 ** attempt), 30.0)
                    jitter = delay * random.uniform(0.5, 1.0)
                    logger.warning(
                        "임베딩 재시도 %d/%d — %s (%.1f초 후)",
                        attempt + 1, max_retries, str(e)[:100], jitter,
                    )
                    await asyncio.sleep(jitter)
                else:
                    self._circuit_breaker.record_failure()
            except Exception as e:
                self._circuit_breaker.record_failure()
                raise EmbeddingServiceError(f"OpenAI embedding failed: {e}") from e

        raise EmbeddingServiceError(f"OpenAI embedding failed after {max_retries} retries: {last_error}") from last_error
