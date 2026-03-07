"use client";

import {
  useQuery,
  useMutation,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";
import { api } from "./api";
import type {
  DocumentListParams,
  SearchRequest,
  DebugSearchResponse,
  RAGSettings,
  PaginationParams,
  Document,
  PaginatedResponse,
  ListResponse,
  Chunk,
  SystemStatus,
  MonitoringStats,
  WatcherStatus,
  EvaluationDataset,
  EvaluationRun,
  EvaluationComparison,
  Trace,
  CostEntry,
  CacheMetrics,
  AvailableModels,
  AdminUser,
} from "@/types";

// ========== Documents ==========

export function useDocuments(params?: DocumentListParams) {
  return useQuery<PaginatedResponse<Document>>({
    queryKey: ["documents", "list", params],
    queryFn: () => api.documents.list(params),
  });
}

export function useDocument(id: string) {
  return useQuery<Document>({
    queryKey: ["documents", "detail", id],
    queryFn: () => api.documents.get(id),
    enabled: !!id,
  });
}

export function useDocumentChunks(id: string) {
  return useQuery<Chunk[]>({
    queryKey: ["documents", "chunks", id],
    queryFn: () => api.documents.chunks(id),
    enabled: !!id,
  });
}

export function useUploadDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ file, metadata }: { file: File; metadata?: Record<string, string> }) =>
      api.documents.upload(file, metadata),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
  });
}

export function useDeleteDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.documents.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
  });
}

export function useReindexDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.documents.reindex(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
  });
}

// ========== Search ==========

export function useSearch() {
  return useMutation<DebugSearchResponse, Error, SearchRequest>({
    mutationFn: (params: SearchRequest) => api.search.queryDebug(params),
  });
}

// ========== Settings ==========

export function useSettings(options?: Partial<UseQueryOptions<RAGSettings>>) {
  return useQuery<RAGSettings>({
    queryKey: ["settings"],
    queryFn: () => api.settings.get(),
    ...options,
  });
}

export function useUpdateSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (settings: Partial<RAGSettings>) => api.settings.update(settings),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["settings"] });
    },
  });
}

export function useModels() {
  return useQuery<AvailableModels>({
    queryKey: ["settings", "models"],
    queryFn: () => api.settings.models(),
  });
}

// ========== Watcher ==========

export function useWatcherStatus() {
  return useQuery<WatcherStatus>({
    queryKey: ["watcher", "status"],
    queryFn: () => api.watcher.status(),
    refetchInterval: 5000,
  });
}

export function useStartWatcher() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.watcher.start(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["watcher"] });
    },
  });
}

export function useStopWatcher() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.watcher.stop(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["watcher"] });
    },
  });
}

export function useScanWatcher() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.watcher.scan(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["watcher"] });
    },
  });
}

// ========== Evaluation ==========

export function useEvaluationDatasets() {
  return useQuery<ListResponse<EvaluationDataset>>({
    queryKey: ["evaluation", "datasets"],
    queryFn: () => api.evaluation.datasets.list(),
  });
}

export function useEvaluationDataset(id: string) {
  return useQuery<EvaluationDataset>({
    queryKey: ["evaluation", "datasets", id],
    queryFn: () => api.evaluation.datasets.get(id),
    enabled: !!id,
  });
}

export function useCreateDataset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { name: string; items: Record<string, unknown>[] }) =>
      api.evaluation.datasets.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["evaluation", "datasets"] });
    },
  });
}

export function useEvaluationRuns() {
  return useQuery<ListResponse<EvaluationRun>>({
    queryKey: ["evaluation", "runs"],
    queryFn: () => api.evaluation.runs.list(),
  });
}

export function useEvaluationRun(id: string) {
  return useQuery<EvaluationRun>({
    queryKey: ["evaluation", "runs", id],
    queryFn: () => api.evaluation.runs.get(id),
    enabled: !!id,
  });
}

export function useRunEvaluation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (datasetId: string) => api.evaluation.run(datasetId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["evaluation", "runs"] });
    },
  });
}

export function useCompareRuns(id1: string, id2: string) {
  return useQuery<EvaluationComparison>({
    queryKey: ["evaluation", "compare", id1, id2],
    queryFn: () => api.evaluation.runs.compare(id1, id2),
    enabled: !!id1 && !!id2,
  });
}

// ========== Monitoring ==========

export function useMonitoringStats() {
  return useQuery<MonitoringStats>({
    queryKey: ["monitoring", "stats"],
    queryFn: () => api.monitoring.stats(),
    refetchInterval: 30000,
  });
}

export function useTraces(params?: PaginationParams) {
  return useQuery<ListResponse<Trace>>({
    queryKey: ["monitoring", "traces", "list", params],
    queryFn: () => api.monitoring.traces(params),
  });
}

export function useTraceDetail(id: string) {
  return useQuery<Trace>({
    queryKey: ["monitoring", "traces", "detail", id],
    queryFn: () => api.monitoring.traceDetail(id),
    enabled: !!id,
  });
}

export function useCosts(params?: { start_date?: string; end_date?: string }) {
  return useQuery<CostEntry>({
    queryKey: ["monitoring", "costs", params],
    queryFn: () => api.monitoring.costs(params),
  });
}

export function useCacheMetrics() {
  return useQuery<CacheMetrics>({
    queryKey: ["monitoring", "cache"],
    queryFn: () => api.monitoring.cache(),
    refetchInterval: 30000,
  });
}

export function useClearCache() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.monitoring.clearCache(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["monitoring", "cache"] });
    },
  });
}

// ========== Auth / Profile ==========

export function useUpdateProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { name?: string; email?: string }) => api.auth.updateProfile(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
    },
  });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: (data: { current_password: string; new_password: string }) =>
      api.auth.changePassword(data),
  });
}

// ========== Admin Users ==========

export function useAdminUsers() {
  return useQuery<{ items: AdminUser[]; total: number }>({
    queryKey: ["admin", "users"],
    queryFn: () => api.admin.listUsers(),
  });
}

export function useCreateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { username: string; name: string; password: string; role: string; email?: string }) =>
      api.admin.createUser(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
    },
  });
}

export function useUpdateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...data }: { id: number; name?: string; email?: string; role?: string; is_active?: boolean }) =>
      api.admin.updateUser(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
    },
  });
}

export function useDeleteUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.admin.deleteUser(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "users"] });
    },
  });
}

// ========== System ==========

export function useSystemStatus() {
  return useQuery<SystemStatus>({
    queryKey: ["system", "status"],
    queryFn: () => api.system.status(),
    refetchInterval: 15000,
  });
}

export function useReindexAll() {
  return useMutation({
    mutationFn: () => api.system.reindexAll(),
  });
}
