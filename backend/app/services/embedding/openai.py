"""OpenAI 임베딩 프로바이더."""
import tiktoken
from openai import AsyncOpenAI

from app.exceptions import EmbeddingServiceError


class OpenAIEmbedding:
    MAX_TOKENS = 8191  # text-embedding-3-small/large 최대 토큰

    def __init__(self, api_key: str, model: str = "text-embedding-3-small", dimensions: int | None = None):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.dimensions = dimensions
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
        try:
            truncated = [self._truncate(t) for t in texts]
            kwargs: dict = {"model": self.model, "input": truncated}
            if self.dimensions:
                kwargs["dimensions"] = self.dimensions
            response = await self.client.embeddings.create(**kwargs)
            return [item.embedding for item in response.data]
        except Exception as e:
            raise EmbeddingServiceError(f"OpenAI embedding failed: {e}") from e

    async def embed_query(self, text: str) -> list[float]:
        results = await self.embed_documents([text])
        return results[0]
