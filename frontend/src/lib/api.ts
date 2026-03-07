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
  AdminUser,
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

// 토큰 관리 — AuthProvider에서 설정
let _getAccessToken: (() => string | null) | null = null;
let _refreshAccessToken: (() => Promise<string | null>) | null = null;
let _onAuthFailure: (() => void) | null = null;

export function setAuthHelpers(helpers: {
  getAccessToken: () => string | null;
  refreshAccessToken: () => Promise<string | null>;
  onAuthFailure: () => void;
}) {
  _getAccessToken = helpers.getAccessToken;
  _refreshAccessToken = helpers.refreshAccessToken;
  _onAuthFailure = helpers.onAuthFailure;
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
    skipAuth?: boolean;
  },
): Promise<T> {
  const url = `${API_BASE}${path}${buildQueryString(options?.params)}`;
  const headers: Record<string, string> = {};

  // Auth header
  if (!options?.skipAuth) {
    const token = _getAccessToken?.();
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
  }

  if (options?.body) {
    headers["Content-Type"] = "application/json";
  }

  const init: RequestInit = {
    method: options?.method || "GET",
    headers,
    credentials: "include",
  };
  if (options?.body) {
    init.body = JSON.stringify(options.body);
  }

  let res = await fetch(url, init);

  // 401 → try refresh
  if (res.status === 401 && !options?.skipAuth && _refreshAccessToken) {
    const newToken = await _refreshAccessToken();
    if (newToken) {
      headers["Authorization"] = `Bearer ${newToken}`;
      init.headers = headers;
      res = await fetch(url, init);
    } else {
      _onAuthFailure?.();
      throw new ApiError(401, "UNAUTHORIZED", "인증이 만료되었습니다.");
    }
  }

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

  const headers: Record<string, string> = {};
  const token = _getAccessToken?.();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(url, {
    method: "POST",
    body: formData,
    headers,
    credentials: "include",
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
  auth: {
    login: (username: string, password: string) =>
      fetchJSON<{ access_token: string }>("/api/auth/login", {
        method: "POST",
        body: { username, password },
        skipAuth: true,
      }),
    signup: (username: string, name: string, password: string, email?: string) =>
      fetchJSON<{ id: number; username: string }>("/api/auth/signup", {
        method: "POST",
        body: { username, name, password, email },
        skipAuth: true,
      }),
    me: () => fetchJSON<{ id: number; username: string; email: string | null; name: string; role: string }>("/api/auth/me"),
    updateProfile: (data: { name?: string; email?: string }) =>
      fetchJSON<{ id: number; username: string; email: string | null; name: string; role: string; is_active: boolean }>("/api/auth/me", {
        method: "PUT",
        body: data,
      }),
    changePassword: (data: { current_password: string; new_password: string }) =>
      fetchJSON<{ message: string }>("/api/auth/me/password", {
        method: "PUT",
        body: data,
      }),
  },
  admin: {
    listUsers: () =>
      fetchJSON<{ items: AdminUser[]; total: number }>("/api/admin/users"),
    createUser: (data: { username: string; name: string; password: string; role: string; email?: string }) =>
      fetchJSON<AdminUser>("/api/admin/users", { method: "POST", body: data }),
    updateUser: (id: number, data: { name?: string; email?: string; role?: string; is_active?: boolean }) =>
      fetchJSON<AdminUser>(`/api/admin/users/${id}`, { method: "PUT", body: data }),
    deleteUser: (id: number) =>
      fetchJSON<{ message: string; id: number }>(`/api/admin/users/${id}`, { method: "DELETE" }),
  },
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
      fetchJSON<HealthCheck>("/api/health", { skipAuth: true }),
    status: () =>
      fetchJSON<SystemStatus>("/api/system/status"),
    reindexAll: () =>
      fetchJSON<{ task_id: string; status: string }>("/api/system/reindex-all", { method: "POST" }),
  },
};

export { ApiError };
