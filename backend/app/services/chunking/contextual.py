"""Contextual Retrieval 청킹: 각 청크에 LLM으로 문맥 요약 추가."""
from app.services.chunking.base import Chunk
from app.services.chunking.recursive import RecursiveChunking
from app.services.generation.base import LLMProvider

CONTEXT_PROMPT = """다음은 전체 문서에서 추출한 하나의 청크입니다.
이 청크가 전체 문서에서 어떤 위치에 있고 무엇을 다루는지 1~2문장으로 간결하게 요약하세요.

전체 문서 앞부분:
{doc_prefix}

현재 청크:
{chunk_content}

요약:"""


class ContextualChunking:
    """기본 재귀 청킹 후 각 청크에 LLM 생성 맥락을 앞에 추가."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
    ):
        self.llm_provider = llm_provider
        self.base_chunker = RecursiveChunking(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    async def chunk(self, text: str, meta: dict | None = None) -> list[Chunk]:
        base_chunks = await self.base_chunker.chunk(text, meta)
        doc_prefix = text[:500]

        enriched = []
        for chunk in base_chunks:
            prompt = CONTEXT_PROMPT.format(
                doc_prefix=doc_prefix,
                chunk_content=chunk.content,
            )
            context = await self.llm_provider.generate(prompt)
            enriched_content = f"{context}\n\n{chunk.content}"
            enriched.append(
                Chunk(
                    content=enriched_content,
                    chunk_index=chunk.chunk_index,
                    metadata=chunk.metadata,
                )
            )

        return enriched
