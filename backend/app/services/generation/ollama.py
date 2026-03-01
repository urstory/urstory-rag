import httpx

from app.exceptions import SearchServiceError


class OllamaLLM:
    def __init__(
        self,
        url: str = "http://localhost:11434",
        model: str = "qwen2.5:7b",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ):
        self.url = url
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    async def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        body: dict = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            },
        }
        if system_prompt:
            body["system"] = system_prompt

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.url}/api/generate",
                    json=body,
                    timeout=120.0,
                )
                response.raise_for_status()
                return response.json()["response"]
        except Exception as e:
            raise SearchServiceError(f"Ollama LLM generation failed: {e}") from e
