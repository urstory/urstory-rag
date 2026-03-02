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
    multi_query_enabled: bool | None = None
    generate_answer: bool = True


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
    detail: dict | None = None


class SearchPipelineResult(BaseModel):
    """하이브리드 검색 오케스트레이터의 반환 타입."""
    documents: list[SearchResult]
    answer: str | None = None
    trace: list[PipelineStep] = []


class DebugSearchResponse(SearchResponse):
    pipeline_trace: list[PipelineStep]


class GuardrailsSettingsResponse(BaseModel):
    pii_detection: dict
    injection_detection: dict
    hallucination_detection: dict
    retrieval_gate: dict
    faithfulness: dict


class SettingsResponse(BaseModel):
    chunking_strategy: str
    chunk_size: int
    chunk_overlap: int
    contextual_chunking_enabled: bool
    contextual_chunking_model: str
    contextual_chunking_max_doc_chars: int
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
    cascading_bm25_threshold: float
    cascading_min_qualifying_docs: int
    cascading_min_doc_score: float
    cascading_fallback_vector_weight: float
    cascading_fallback_keyword_weight: float
    query_expansion_enabled: bool
    query_expansion_max_keywords: int
    multi_query_enabled: bool
    multi_query_count: int
    multi_query_model: str
    exact_citation_enabled: bool
    numeric_verification_enabled: bool
    guardrails: GuardrailsSettingsResponse
    pii_detection_enabled: bool
    injection_detection_enabled: bool
    hallucination_detection_enabled: bool
    retrieval_quality_gate_enabled: bool
    faithfulness_enabled: bool
    llm_provider: str
    llm_model: str
    system_prompt: str


class SettingsUpdateRequest(BaseModel):
    chunking_strategy: str | None = None
    chunk_size: int | None = None
    chunk_overlap: int | None = None
    contextual_chunking_enabled: bool | None = None
    contextual_chunking_model: str | None = None
    contextual_chunking_max_doc_chars: int | None = None
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
    cascading_bm25_threshold: float | None = None
    cascading_min_qualifying_docs: int | None = None
    cascading_min_doc_score: float | None = None
    cascading_fallback_vector_weight: float | None = None
    cascading_fallback_keyword_weight: float | None = None
    query_expansion_enabled: bool | None = None
    query_expansion_max_keywords: int | None = None
    multi_query_enabled: bool | None = None
    multi_query_count: int | None = None
    multi_query_model: str | None = None
    exact_citation_enabled: bool | None = None
    numeric_verification_enabled: bool | None = None
    guardrails: dict | None = None
    pii_detection_enabled: bool | None = None
    injection_detection_enabled: bool | None = None
    hallucination_detection_enabled: bool | None = None
    retrieval_quality_gate_enabled: bool | None = None
    faithfulness_enabled: bool | None = None
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
