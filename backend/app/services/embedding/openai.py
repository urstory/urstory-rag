"""OpenAI 임베딩 프로바이더."""
from openai import AsyncOpenAI

from app.exceptions import EmbeddingServiceError


class OpenAIEmbedding:
    def __init__(self, api_key: str, model: str = "text-embedding-3-small", dimensions: int | None = None):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.dimensions = dimensions

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        try:
            kwargs: dict = {"model": self.model, "input": texts}
            if self.dimensions:
                kwargs["dimensions"] = self.dimensions
            response = await self.client.embeddings.create(**kwargs)
            return [item.embedding for item in response.data]
        except Exception as e:
            raise EmbeddingServiceError(f"OpenAI embedding failed: {e}") from e

    async def embed_query(self, text: str) -> list[float]:
        results = await self.embed_documents([text])
        return results[0]
