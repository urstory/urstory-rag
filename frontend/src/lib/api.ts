import type {
  PaginatedResponse,
  Document,
  DocumentListParams,
  Chunk,
  SearchRequest,
  SearchResponse,
  DebugSearchResponse,
  RAGSettings,
  ModelInfo,
  WatcherStatus,
  WatchedFile,
  PaginationParams,
  EvaluationDataset,
  EvaluationRun,
  EvaluationComparison,
  MonitoringStats,
  Trace,
  CostEntry,
  SystemStatus,
  HealthCheck,
  AsyncTask,
} from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function buildQueryString(params?: Record<string, unknown>): string {
  if (!params) return "";
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null) {
      searchParams.set(key, String(value));
    }
  }
  const qs = searchParams.toString();
  return qs ? `?${qs}` : "";
}

async function fetchJSON<T>(
  path: string,
  options?: {
    method?: string;
    body?: unknown;
    params?: Record<string, unknown>;
  },
): Promise<T> {
  const url = `${API_BASE}${path}${buildQueryString(options?.params)}`;
  const init: RequestInit = {
    method: options?.method || "GET",
    headers: {
      "Content-Type": "application/json",
    },
  };
  if (options?.body) {
    init.body = JSON.stringify(options.body);
  }
  const res = await fetch(url, init);
  if (!res.ok) {
    let errorData: { error?: string; message?: string } = {};
    try {
      errorData = await res.json();
    } catch {
      // ignore parse error
    }
    throw new ApiError(
      res.status,
      errorData.error || "UNKNOWN",
      errorData.message || res.statusText,
    );
  }
  return res.json() as Promise<T>;
}

async function fetchFormData<T>(
  path: string,
  file: File,
  metadata?: Record<string, string>,
): Promise<T> {
  const url = `${API_BASE}${path}`;
  const formData = new FormData();
  formData.append("file", file);
  if (metadata) {
    formData.append("metadata", JSON.stringify(metadata));
  }
  const res = await fetch(url, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    let errorData: { error?: string; message?: string } = {};
    try {
      errorData = await res.json();
    } catch {
      // ignore parse error
    }
    throw new ApiError(
      res.status,
      errorData.error || "UNKNOWN",
      errorData.message || res.statusText,
    );
  }
  return res.json() as Promise<T>;
}

export const api = {
  documents: {
    list: (params?: DocumentListParams) =>
      fetchJSON<PaginatedResponse<Document>>("/api/documents", { params: params as Record<string, unknown> }),
    upload: (file: File, metadata?: Record<string, string>) =>
      fetchFormData<Document>("/api/documents/upload", file, metadata),
    get: (id: string) =>
      fetchJSON<Document>(`/api/documents/${id}`),
    delete: (id: string) =>
      fetchJSON<void>(`/api/documents/${id}`, { method: "DELETE" }),
    reindex: (id: string) =>
      fetchJSON<AsyncTask>(`/api/documents/${id}/reindex`, { method: "POST" }),
    chunks: (id: string) =>
      fetchJSON<Chunk[]>(`/api/documents/${id}/chunks`),
  },
  search: {
    query: (params: SearchRequest) =>
      fetchJSON<SearchResponse>("/api/search", { method: "POST", body: params }),
    queryDebug: (params: SearchRequest) =>
      fetchJSON<DebugSearchResponse>("/api/search/debug", { method: "POST", body: params }),
  },
  settings: {
    get: () =>
      fetchJSON<RAGSettings>("/api/settings"),
    update: (settings: Partial<RAGSettings>) =>
      fetchJSON<RAGSettings>("/api/settings", { method: "PATCH", body: settings }),
    models: () =>
      fetchJSON<ModelInfo[]>("/api/settings/models"),
  },
  evaluation: {
    datasets: {
      list: () =>
        fetchJSON<PaginatedResponse<EvaluationDataset>>("/api/evaluation/datasets"),
      create: (data: FormData) => {
        const url = `${API_BASE}/api/evaluation/datasets`;
        return fetch(url, { method: "POST", body: data }).then((res) => {
          if (!res.ok) throw new ApiError(res.status, "UPLOAD_ERROR", res.statusText);
          return res.json() as Promise<EvaluationDataset>;
        });
      },
      get: (id: string) =>
        fetchJSON<EvaluationDataset>("/api/evaluation/datasets/" + id),
    },
    runs: {
      list: () =>
        fetchJSON<PaginatedResponse<EvaluationRun>>("/api/evaluation/runs"),
      get: (id: string) =>
        fetchJSON<EvaluationRun>(`/api/evaluation/runs/${id}`),
      compare: (id1: string, id2: string) =>
        fetchJSON<EvaluationComparison>(`/api/evaluation/runs/${id1}/compare/${id2}`),
    },
    run: (datasetId: string) =>
      fetchJSON<AsyncTask>("/api/evaluation/run", { method: "POST", body: { dataset_id: datasetId } }),
  },
  monitoring: {
    stats: () =>
      fetchJSON<MonitoringStats>("/api/monitoring/stats"),
    traces: (params?: PaginationParams) =>
      fetchJSON<PaginatedResponse<Trace>>("/api/monitoring/traces", { params: params as Record<string, unknown> }),
    traceDetail: (id: string) =>
      fetchJSON<Trace>(`/api/monitoring/traces/${id}`),
    costs: (params?: { start_date?: string; end_date?: string }) =>
      fetchJSON<CostEntry[]>("/api/monitoring/costs", { params: params as Record<string, unknown> }),
  },
  watcher: {
    status: () =>
      fetchJSON<WatcherStatus>("/api/watcher/status"),
    start: () =>
      fetchJSON<{ status: string }>("/api/watcher/start", { method: "POST" }),
    stop: () =>
      fetchJSON<{ status: string }>("/api/watcher/stop", { method: "POST" }),
    scan: () =>
      fetchJSON<AsyncTask>("/api/watcher/scan", { method: "POST" }),
    files: (params?: PaginationParams) =>
      fetchJSON<PaginatedResponse<WatchedFile>>("/api/watcher/files", { params: params as Record<string, unknown> }),
  },
  system: {
    health: () =>
      fetchJSON<HealthCheck>("/api/health"),
    status: () =>
      fetchJSON<SystemStatus>("/api/system/status"),
    reindexAll: () =>
      fetchJSON<AsyncTask>("/api/system/reindex-all", { method: "POST" }),
  },
};

export { ApiError };
