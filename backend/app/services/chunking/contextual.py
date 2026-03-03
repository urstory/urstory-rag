"""Contextual Retrieval 청킹: 각 청크에 LLM으로 문맥 요약 추가.

데코레이터 패턴: 어떤 ChunkingStrategy든 받아서 감쌀 수 있다.
"""
import asyncio

from app.services.chunking.base import Chunk, ChunkingStrategy
from app.services.generation.base import LLMProvider

CONTEXT_PROMPT = """이 청크가 속한 문서의 구조적 경로와 검색 키워드를 작성하세요.

형식:
[문서 주제] > [섹션] > [하위 섹션]
키워드: (이 청크의 검색에 도움이 될 한국어 키워드 3~5개)

규칙:
- 표가 포함되어 있으면 표 제목이나 규정명을 키워드에 포함하세요.
- 고유명사, 숫자 조건, 등급/기준은 반드시 키워드에 포함하세요.
- 경로와 키워드 외 다른 설명은 불필요합니다.

예시:
장기요양 등급판정 > 인정기준 > 등급 유지 조건
키워드: 호전율, 기준점수, 재심사, 등급유지율, 우수

전체 문서 앞부분:
{doc_prefix}

현재 청크:
{chunk_content}

경로와 키워드:"""


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
