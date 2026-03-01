"""청킹 전략 인터페이스 및 Chunk 데이터 클래스."""
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class Chunk:
    content: str
    chunk_index: int
    metadata: dict = field(default_factory=dict)


@runtime_checkable
class ChunkingStrategy(Protocol):
    async def chunk(self, text: str, meta: dict | None = None) -> list[Chunk]: ...
