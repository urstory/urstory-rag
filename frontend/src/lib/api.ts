import type {
  PaginatedResponse,
  ListResponse,
  Document,
  DocumentListParams,
  Chunk,
  ChunksResponse,
  UploadResponse,
  DeleteResponse,
  ReindexResponse,
  SearchRequest,
  DebugSearchResponse,
  RAGSettings,
  AvailableModels,
  WatcherStatus,
  WatcherActionResponse,
  WatcherScanResponse,
  PaginationParams,
  EvaluationDataset,
  EvaluationRun,
  EvaluationComparison,
  MonitoringStats,
  Trace,
  CostEntry,
  SystemStatus,
  HealthCheck,
} from "@/types";

const API_BASE = "";

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
    if (value !== undefined && value !== null && typeof value !== "object") {
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
  const headers: Record<string, string> = {};
  if (options?.body) {
    headers["Content-Type"] = "application/json";
  }
  const init: RequestInit = {
    method: options?.method || "GET",
    headers,
  };
  if (options?.body) {
    init.body = JSON.stringify(options.body);
  }
  const res = await fetch(url, init);
  if (!res.ok) {
    let errorData: { error?: string; message?: string; detail?: string } = {};
    try {
      errorData = await res.json();
    } catch {
      // ignore parse error
    }
    throw new ApiError(
      res.status,
      errorData.error || "UNKNOWN",
      errorData.message || errorData.detail || res.statusText,
    );
  }
  if (res.status === 204) return undefined as T;
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
    let errorData: { error?: string; message?: string; detail?: string } = {};
    try {
      errorData = await res.json();
    } catch {
      // ignore parse error
    }
    throw new ApiError(
      res.status,
      errorData.error || "UNKNOWN",
      errorData.message || errorData.detail || res.statusText,
    );
  }
  return res.json() as Promise<T>;
}

export const api = {
  documents: {
    list: (params?: DocumentListParams) => {
      const { source, ...rest } = params ?? {};
      const query: Record<string, unknown> = { ...rest };
      if (source && source !== "all") query.source = source;
      return fetchJSON<PaginatedResponse<Document>>("/api/documents", { params: query });
    },
    upload: (file: File, metadata?: Record<string, string>) =>
      fetchFormData<UploadResponse>("/api/documents/upload", file, metadata),
    get: (id: string) =>
      fetchJSON<Document>(`/api/documents/${id}`),
    delete: (id: string) =>
      fetchJSON<DeleteResponse>(`/api/documents/${id}`, { method: "DELETE" }),
    reindex: (id: string) =>
      fetchJSON<ReindexResponse>(`/api/documents/${id}/reindex`, { method: "POST" }),
    chunks: (id: string) =>
      fetchJSON<ChunksResponse>(`/api/documents/${id}/chunks`).then((r) => r.chunks),
  },
  search: {
    query: (params: SearchRequest) =>
      fetchJSON<DebugSearchResponse>("/api/search", { method: "POST", body: params }),
    queryDebug: (params: SearchRequest) =>
      fetchJSON<DebugSearchResponse>("/api/search/debug", { method: "POST", body: params }),
  },
  settings: {
    get: () =>
      fetchJSON<RAGSettings>("/api/settings"),
    update: (settings: Partial<RAGSettings>) =>
      fetchJSON<RAGSettings>("/api/settings", { method: "PATCH", body: settings }),
    models: () =>
      fetchJSON<AvailableModels>("/api/settings/models"),
  },
  evaluation: {
    datasets: {
      list: () =>
        fetchJSON<ListResponse<EvaluationDataset>>("/api/evaluation/datasets"),
      create: (data: { name: string; items: Record<string, unknown>[] }) =>
        fetchJSON<EvaluationDataset>("/api/evaluation/datasets", { method: "POST", body: data }),
      get: (id: string) =>
        fetchJSON<EvaluationDataset>("/api/evaluation/datasets/" + id),
    },
    runs: {
      list: () =>
        fetchJSON<ListResponse<EvaluationRun>>("/api/evaluation/runs"),
      get: (id: string) =>
        fetchJSON<EvaluationRun>(`/api/evaluation/runs/${id}`),
      compare: (id1: string, id2: string) =>
        fetchJSON<EvaluationComparison>(`/api/evaluation/runs/${id1}/compare/${id2}`),
    },
    run: (datasetId: string) =>
      fetchJSON<EvaluationRun>("/api/evaluation/run", { method: "POST", body: { dataset_id: datasetId } }),
  },
  monitoring: {
    stats: () =>
      fetchJSON<MonitoringStats>("/api/monitoring/stats"),
    traces: (params?: PaginationParams) =>
      fetchJSON<ListResponse<Trace>>("/api/monitoring/traces", { params: params as Record<string, unknown> }),
    traceDetail: (id: string) =>
      fetchJSON<Trace>(`/api/monitoring/traces/${id}`),
    costs: (params?: { start_date?: string; end_date?: string }) =>
      fetchJSON<CostEntry>("/api/monitoring/costs", { params: params as Record<string, unknown> }),
  },
  watcher: {
    status: () =>
      fetchJSON<WatcherStatus>("/api/watcher/status"),
    start: (directories?: string[], usePolling?: boolean) =>
      fetchJSON<WatcherActionResponse>(`/api/watcher/start${buildQueryString({
        directories: undefined,
        use_polling: usePolling,
      })}`, {
        method: "POST",
        params: { ...(directories ? { directories: directories.join(",") } : {}), ...(usePolling ? { use_polling: "true" } : {}) },
      }),
    stop: () =>
      fetchJSON<WatcherActionResponse>("/api/watcher/stop", { method: "POST" }),
    scan: () =>
      fetchJSON<WatcherScanResponse>("/api/watcher/scan", { method: "POST" }),
  },
  system: {
    health: () =>
      fetchJSON<HealthCheck>("/api/health"),
    status: () =>
      fetchJSON<SystemStatus>("/api/system/status"),
    reindexAll: () =>
      fetchJSON<{ task_id: string; status: string }>("/api/system/reindex-all", { method: "POST" }),
  },
};

export { ApiError };
