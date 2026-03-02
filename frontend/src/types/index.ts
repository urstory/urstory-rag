// ========== Common ==========

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  pages: number;
}

export interface PaginationParams {
  page?: number;
  size?: number;
  sort?: string;
  order?: "asc" | "desc";
}

export interface AsyncTask {
  task_id: string;
  status: "pending" | "running" | "completed" | "failed";
  progress: number;
  result: unknown;
  error: string | null;
  created_at: string;
  updated_at: string;
}

// ========== Documents ==========

export interface Document {
  id: string;
  filename: string;
  file_type: string;
  file_size: number;
  status: "pending" | "processing" | "indexed" | "failed";
  chunk_count: number;
  source: "upload" | "watcher";
  metadata: Record<string, string>;
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
  document_id: string;
  content: string;
  chunk_index: number;
  metadata: Record<string, unknown>;
  embedding_status: string;
}

// ========== Search ==========

export interface SearchRequest {
  query: string;
  top_k?: number;
  search_mode?: "hybrid" | "vector" | "keyword" | "cascading";
  use_hyde?: boolean;
  use_reranking?: boolean;
  generate_answer?: boolean;
}

export interface SearchResultDocument {
  id: string;
  content: string;
  score: number;
  meta: {
    doc_id: string;
    doc_name: string;
    chunk_index: number;
  };
}

export interface SearchResponse {
  answer: string;
  documents: SearchResultDocument[];
  trace_id: string;
}

export interface PipelineStep {
  passed?: boolean;
  enabled?: boolean;
  generated_document?: string;
  results_count?: number;
  input_count?: number;
  output_count?: number;
  duration_ms?: number;
  model?: string;
  tokens?: { prompt: number; completion: number };
  confidence?: number;
}

export interface PipelineTrace {
  guardrail_input: PipelineStep;
  hyde: PipelineStep;
  vector_search: PipelineStep;
  keyword_search: PipelineStep;
  cascading_eval_stage1: PipelineStep;
  query_expansion: PipelineStep;
  keyword_search_expanded: PipelineStep;
  cascading_eval_stage2: PipelineStep;
  cascading_vector_fallback: PipelineStep;
  rrf_fusion: PipelineStep;
  reranking: PipelineStep;
  retrieval_gate: PipelineStep;
  guardrail_pii: PipelineStep;
  generation: PipelineStep;
  guardrail_faithfulness: PipelineStep;
  guardrail_hallucination: PipelineStep;
  total_duration_ms: number;
}

export interface DebugSearchResponse extends SearchResponse {
  pipeline_trace: PipelineTrace;
}

// ========== Settings ==========

export interface ChunkingSettings {
  strategy: string;
  chunk_size: number;
  chunk_overlap: number;
}

export interface EmbeddingSettings {
  provider: string;
  model: string;
}

export interface SearchSettings {
  mode: "hybrid" | "vector" | "keyword" | "cascading";
  keyword_engine: string;
  rrf_constant: number;
  vector_weight: number;
  keyword_weight: number;
  cascading_bm25_threshold: number;
  cascading_min_qualifying_docs: number;
  cascading_min_doc_score: number;
  cascading_fallback_vector_weight: number;
  cascading_fallback_keyword_weight: number;
  query_expansion_enabled: boolean;
  query_expansion_max_keywords: number;
}

export interface RerankingSettings {
  enabled: boolean;
  model: string;
  top_k: number;
  retriever_top_k: number;
}

export interface HyDESettings {
  enabled: boolean;
  model: string;
  apply_mode: "all" | "long_query" | "complex";
}

export interface GuardrailSettings {
  pii_detection: boolean;
  injection_detection: boolean;
  hallucination_detection: boolean;
}

export interface GenerationSettings {
  provider: string;
  model: string;
  system_prompt: string;
  temperature: number;
  max_tokens: number;
}

export interface WatcherSettings {
  enabled: boolean;
  directories: string[];
  use_polling: boolean;
  polling_interval: number;
  auto_delete: boolean;
  file_patterns: string[];
}

export interface RAGSettings {
  chunking: ChunkingSettings;
  embedding: EmbeddingSettings;
  search: SearchSettings;
  reranking: RerankingSettings;
  hyde: HyDESettings;
  guardrails: GuardrailSettings;
  generation: GenerationSettings;
  watcher: WatcherSettings;
}

export interface ModelInfo {
  name: string;
  provider: string;
  type: "embedding" | "generation" | "reranking";
}

// ========== Watcher ==========

export interface WatcherLastEvent {
  type: string;
  path: string;
  timestamp: string;
}

export interface WatcherStats {
  total_synced: number;
  pending: number;
  failed: number;
}

export interface WatcherStatus {
  status: "running" | "stopped";
  directories: string[];
  mode: string;
  watched_file_count: number;
  last_event: WatcherLastEvent | null;
  stats: WatcherStats;
}

export interface WatchedFile {
  id: string;
  path: string;
  filename: string;
  file_type: string;
  file_size: number;
  status: "synced" | "pending" | "failed";
  document_id: string | null;
  last_modified: string;
  synced_at: string | null;
}

// ========== Evaluation ==========

export interface EvaluationDataset {
  id: string;
  name: string;
  description: string;
  qa_count: number;
  created_at: string;
}

export interface QAPair {
  question: string;
  ground_truth: string;
}

export interface EvaluationMetrics {
  faithfulness: number;
  answer_relevancy: number;
  context_precision: number;
  context_recall: number;
}

export interface PerQuestionResult {
  question: string;
  ground_truth: string;
  answer: string;
  faithfulness: number;
  answer_relevancy: number;
  context_precision: number;
  context_recall: number;
}

export interface EvaluationRun {
  id: string;
  dataset_id: string;
  dataset_name?: string;
  status: "pending" | "running" | "completed" | "failed";
  settings_snapshot: Partial<RAGSettings>;
  metrics: EvaluationMetrics;
  per_question_results: PerQuestionResult[];
  created_at: string;
}

export interface EvaluationComparison {
  run1: EvaluationRun;
  run2: EvaluationRun;
  metric_diffs: EvaluationMetrics;
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
  date: string;
  provider: string;
  model: string;
  tokens_in: number;
  tokens_out: number;
  cost_usd: number;
}

// ========== System ==========

export interface ComponentStatus {
  name: string;
  status: "connected" | "disconnected" | "error";
  latency_ms?: number;
  details?: string;
}

export interface SystemStatus {
  status: "healthy" | "degraded" | "unhealthy";
  components: ComponentStatus[];
  uptime_seconds: number;
}

export interface HealthCheck {
  status: string;
  version: string;
}
