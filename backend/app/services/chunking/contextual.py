"""Contextual Retrieval 청킹: 각 청크에 LLM으로 문맥 요약 추가.

데코레이터 패턴: 어떤 ChunkingStrategy든 받아서 감쌀 수 있다.
"""
import asyncio

from app.services.chunking.base import Chunk, ChunkingStrategy
from app.services.generation.base import LLMProvider

CONTEXT_PROMPT = """다음은 전체 문서에서 추출한 하나의 청크입니다.
이 청크가 전체 문서에서 어떤 위치에 있고 무엇을 다루는지 1~2문장으로 간결하게 요약하세요.

전체 문서 앞부분:
{doc_prefix}

현재 청크:
{chunk_content}

요약:"""


class ContextualChunking:
    """기본 청킹 전략 위에 LLM 생성 맥락을 추가하는 데코레이터."""

    def __init__(
        self,
        llm_provider: LLMProvider,
        base_strategy: ChunkingStrategy,
        max_doc_chars: int = 2000,
        max_concurrent: int = 5,
    ):
        self.llm_provider = llm_provider
        self.base_strategy = base_strategy
        self.max_doc_chars = max_doc_chars
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def chunk(self, text: str, meta: dict | None = None) -> list[Chunk]:
        base_chunks = await self.base_strategy.chunk(text, meta)
        doc_prefix = text[:self.max_doc_chars]

        async def enrich_chunk(chunk: Chunk) -> Chunk:
            async with self._semaphore:
                try:
                    prompt = CONTEXT_PROMPT.format(
                        doc_prefix=doc_prefix,
                        chunk_content=chunk.content,
                    )
                    context = await self.llm_provider.generate(prompt)
                    enriched_meta = {**chunk.metadata, "contextual": True}
                    return Chunk(
                        content=f"{context}\n\n{chunk.content}",
                        chunk_index=chunk.chunk_index,
                        metadata=enriched_meta,
                    )
                except Exception:
                    # LLM 실패 시 원본 청크 유지
                    return chunk

        results = await asyncio.gather(*(enrich_chunk(c) for c in base_chunks))
        return list(results)
