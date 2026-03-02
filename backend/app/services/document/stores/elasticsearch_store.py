"""Elasticsearch 스토어: 청크를 ES 인덱스에 저장 (Nori 분석기)."""
from __future__ import annotations

import json
import uuid

import httpx

from app.services.chunking.base import Chunk

_INDEX_SETTINGS = {
    "settings": {
        "analysis": {
            "analyzer": {
                "nori_analyzer": {
                    "type": "custom",
                    "tokenizer": "nori_tokenizer",
                    "filter": ["nori_readingform", "lowercase"],
                }
            }
        }
    },
    "mappings": {
        "properties": {
            "content": {"type": "text", "analyzer": "nori_analyzer"},
            "document_id": {"type": "keyword"},
            "chunk_id": {"type": "keyword"},
            "chunk_index": {"type": "integer"},
            "metadata": {"type": "object", "enabled": True},
        }
    },
}


class ElasticsearchStore:
    """Elasticsearch 청크 저장소."""

    def __init__(
        self,
        es_url: str = "http://localhost:9200",
        index_name: str = "rag_chunks",
    ) -> None:
        self.es_url = es_url
        self.index_name = index_name

    async def write(self, chunks: list[Chunk], meta: dict) -> None:
        """청크를 Elasticsearch에 bulk 인덱싱."""
        doc_id = meta["doc_id"]

        async with httpx.AsyncClient() as client:
            await self._ensure_index(client)

            bulk_body = ""
            for chunk in chunks:
                chunk_id = str(uuid.uuid4())
                action = json.dumps(
                    {"index": {"_index": self.index_name, "_id": chunk_id}},
                    ensure_ascii=False,
                )
                doc = json.dumps(
                    {
                        "chunk_id": chunk_id,
                        "document_id": doc_id,
                        "content": chunk.content,
                        "chunk_index": chunk.chunk_index,
                        "metadata": chunk.metadata or {},
                    },
                    ensure_ascii=False,
                )
                bulk_body += action + "\n" + doc + "\n"

            if bulk_body:
                resp = await client.post(
                    f"{self.es_url}/_bulk",
                    content=bulk_body,
                    headers={"Content-Type": "application/x-ndjson"},
                    timeout=60.0,
                )
                resp.raise_for_status()

    async def delete(self, filters: dict) -> None:
        """특정 문서의 청크를 ES에서 삭제."""
        doc_id = filters["doc_id"]
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.es_url}/{self.index_name}/_delete_by_query",
                json={"query": {"term": {"document_id": doc_id}}},
                timeout=30.0,
            )
            if resp.status_code != 404:
                resp.raise_for_status()

    async def _ensure_index(self, client: httpx.AsyncClient) -> None:
        """인덱스가 없으면 Nori 분석기 매핑으로 생성."""
        resp = await client.head(f"{self.es_url}/{self.index_name}", timeout=10.0)
        if resp.status_code == 404:
            resp = await client.put(
                f"{self.es_url}/{self.index_name}",
                json=_INDEX_SETTINGS,
                timeout=10.0,
            )
            resp.raise_for_status()
