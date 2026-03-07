// ========== Common ==========

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

/** 페이지네이션 없는 단순 목록 응답 */
export interface ListResponse<T> {
  items: T[];
  total: number;
}

export interface PaginationParams {
  page?: number;
  size?: number;
  sort?: string;
  order?: "asc" | "desc";
}

// ========== Admin / Users ==========

export interface AdminUser {
  id: number;
  username: string;
  email: string | null;
  name: string;
  role: string;
  is_active: boolean;
  created_at: string | null;
}

// ========== Documents ==========

export interface Document {
  id: string;
  filename: string;
  file_type: string;
  file_size: number;
  status: string;
  chunk_count: number | null;
  source: string;
  created_at: string;
  updated_at: string;
}

export interface DocumentListParams extends PaginationParams {
  source?: "all" | "upload" | "watcher";
  status?: string;
  search?: string;
}

export interface Chunk {
  id: string;
  chunk_index: number;
  content: string;
  metadata: Record<string, unknown> | null;
}

/** /api/documents/:id/chunks 래퍼 응답 */
export interface ChunksResponse {
  document_id: string;
  chunks: Chunk[];
}

/** /api/documents/upload 응답 */
export interface UploadResponse {
  id: string;
  status: string;
  filename: string;
}

/** /api/documents/:id (DELETE) 응답 */
export interface DeleteResponse {
  message: string;
  id: string;
}

/** /api/documents/:id/reindex 응답 */
export interface ReindexResponse {
  id: string;
  status: string;
}

// ========== Search ==========

export interface SearchRequest {
  query: string;
  top_k?: number;
  search_mode?: "hybrid" | "vector" | "keyword" | "cascading";
  hyde_enabled?: boolean;
  reranking_enabled?: boolean;
  multi_query_enabled?: boolean;
  generate_answer?: boolean;
}

export interface SearchResult {
  chunk_id: string;
  document_id: string;
  content: string;
  score: number;
  metadata?: Record<string, unknown> | null;
}

export interface SearchResponse {
  query: string;
  answer: string;
  results: SearchResult[];
}

export interface PipelineStep {
  name: string;
  passed: boolean;
  duration_ms: number;
  results_count?: number | null;
  detail?: Record<string, unknown> | null;
}

export interface DebugSearchResponse extends SearchResponse {
  pipeline_trace: PipelineStep[];
}

// ========== Settings ==========

export interface RAGSettings {
  // 청킹
  chunking_strategy: string;
  chunk_size: number;
  chunk_overlap: number;
  contextual_chunking_enabled: boolean;
  contextual_chunking_model: string;
  contextual_chunking_max_doc_chars: number;
  // 임베딩
  embedding_provider: string;
  embedding_model: string;
  // 검색
  search_mode: string;
  keyword_engine: string;
  rrf_constant: number;
  vector_weight: number;
  keyword_weight: number;
  // 리랭킹
  reranking_enabled: boolean;
  reranker_model: string;
  reranker_top_k: number;
  retriever_top_k: number;
  // HyDE
  hyde_enabled: boolean;
  hyde_model: string;
  // Cascading + Query Expansion
  cascading_bm25_threshold: number;
  cascading_min_qualifying_docs: number;
  cascading_min_doc_score: number;
  cascading_fallback_vector_weight: number;
  cascading_fallback_keyword_weight: number;
  query_expansion_enabled: boolean;
  query_expansion_max_keywords: number;
  // 멀티쿼리
  multi_query_enabled: boolean;
  multi_query_count: number;
  multi_query_model: string;
  // 가드레일
  exact_citation_enabled: boolean;
  numeric_verification_enabled: boolean;
  pii_detection_enabled: boolean;
  injection_detection_enabled: boolean;
  hallucination_detection_enabled: boolean;
  retrieval_quality_gate_enabled: boolean;
  faithfulness_enabled: boolean;
  // LLM
  llm_provider: string;
  llm_model: string;
  system_prompt: string;
  // 백엔드가 추가로 반환하는 필드 (읽기전용)
  guardrails?: Record<string, unknown>;
}

/** /api/settings/models 응답: Record<string, string[]> */
export type AvailableModels = Record<string, string[]>;

// ========== Watcher ==========

/** 실제 백엔드 GET /api/watcher/status 응답 */
export interface WatcherStatus {
  running: boolean;
  directories: string[];
}

/** POST /api/watcher/start|stop 응답 */
export interface WatcherActionResponse {
  message: string;
  running: boolean;
  directories?: string[];
}

/** POST /api/watcher/scan 응답 */
export interface WatcherScanResponse {
  scanned_files: number;
  directories: string[];
}

// ========== Evaluation ==========

export interface EvaluationDataset {
  id: string;
  name: string;
  items: Record<string, unknown>[];
  created_at: string | null;
}

export interface EvaluationMetrics {
  faithfulness: number;
  answer_relevancy: number;
  context_precision: number;
  context_recall: number;
}

export interface PerQuestionResult {
  question: string;
  ground_truth?: string;
  answer?: string;
  faithfulness: number;
  answer_relevancy: number;
  context_precision: number;
  context_recall: number;
}

export interface EvaluationRun {
  id: string;
  dataset_id: string;
  dataset_name?: string;
  status: string;
  settings_snapshot: Record<string, unknown> | null;
  metrics: EvaluationMetrics | null;
  per_question_results: PerQuestionResult[] | null;
  created_at: string | null;
}

export interface EvaluationComparison {
  run1: EvaluationRun;
  run2: EvaluationRun;
  diff: Record<string, number>;
}

// ========== Monitoring ==========

export interface MonitoringStats {
  total_documents: number;
  total_chunks: number;
  today_queries: number;
  avg_response_time_ms: number;
}

export interface TraceSpan {
  name: string;
  duration_ms: number;
  status: string;
  metadata?: Record<string, unknown>;
}

export interface Trace {
  id: string;
  query: string;
  total_duration_ms: number;
  status: "success" | "error";
  spans: TraceSpan[];
  created_at: string;
}

export interface CostEntry {
  total_cost: number;
  period: string;
  breakdown: Record<string, unknown>[];
}

// ========== System ==========

/** GET /api/system/status — components 값은 boolean */
export interface SystemStatus {
  status: string;
  components: Record<string, boolean>;
}

/** GET /api/health 응답 */
export interface HealthCheck {
  status: string;
  components?: Record<string, string>;
}
