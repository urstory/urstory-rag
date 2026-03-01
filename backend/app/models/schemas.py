import uuid
from datetime import datetime

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    components: dict[str, str] | None = None


class DocumentResponse(BaseModel):
    id: uuid.UUID
    filename: str
    file_path: str
    file_type: str
    file_size: int
    status: str
    chunk_count: int | None = None
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int
    page: int
    page_size: int


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5
    search_mode: str | None = None
    hyde_enabled: bool | None = None
    reranking_enabled: bool | None = None


class SearchResult(BaseModel):
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    content: str
    score: float
    metadata: dict | None = None


class SearchResponse(BaseModel):
    query: str
    answer: str
    results: list[SearchResult]


class PipelineStep(BaseModel):
    name: str
    passed: bool
    duration_ms: float
    results_count: int | None = None


class DebugSearchResponse(SearchResponse):
    pipeline_trace: list[PipelineStep]


class SettingsResponse(BaseModel):
    chunking_strategy: str
    chunk_size: int
    chunk_overlap: int
    embedding_provider: str
    embedding_model: str
    search_mode: str
    keyword_engine: str
    rrf_constant: int
    vector_weight: float
    keyword_weight: float
    reranking_enabled: bool
    reranker_model: str
    reranker_top_k: int
    retriever_top_k: int
    hyde_enabled: bool
    hyde_model: str
    pii_detection_enabled: bool
    injection_detection_enabled: bool
    hallucination_detection_enabled: bool
    llm_provider: str
    llm_model: str
    system_prompt: str


class SettingsUpdateRequest(BaseModel):
    chunking_strategy: str | None = None
    chunk_size: int | None = None
    chunk_overlap: int | None = None
    embedding_provider: str | None = None
    embedding_model: str | None = None
    search_mode: str | None = None
    keyword_engine: str | None = None
    rrf_constant: int | None = None
    vector_weight: float | None = None
    keyword_weight: float | None = None
    reranking_enabled: bool | None = None
    reranker_model: str | None = None
    reranker_top_k: int | None = None
    retriever_top_k: int | None = None
    hyde_enabled: bool | None = None
    hyde_model: str | None = None
    pii_detection_enabled: bool | None = None
    injection_detection_enabled: bool | None = None
    hallucination_detection_enabled: bool | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    system_prompt: str | None = None


class TaskStatusResponse(BaseModel):
    id: uuid.UUID
    type: str
    status: str
    progress: int
    result: dict | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime
