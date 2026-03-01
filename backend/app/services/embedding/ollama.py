import httpx

from app.exceptions import EmbeddingServiceError


class OllamaEmbedding:
    def __init__(self, url: str = "http://localhost:11434", model: str = "bge-m3"):
        self.url = url
        self.model = model

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.url}/api/embed",
                    json={"model": self.model, "input": texts},
                    timeout=120.0,
                )
                response.raise_for_status()
                return response.json()["embeddings"]
        except Exception as e:
            raise EmbeddingServiceError(f"Ollama embedding failed: {e}") from e

    async def embed_query(self, text: str) -> list[float]:
        results = await self.embed_documents([text])
        return results[0]
