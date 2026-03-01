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
  Chunk,
  SystemStatus,
  MonitoringStats,
  WatcherStatus,
  EvaluationDataset,
  EvaluationRun,
  EvaluationComparison,
  Trace,
  CostEntry,
  WatchedFile,
  ModelInfo,
} from "@/types";

// ========== Documents ==========

export function useDocuments(params?: DocumentListParams) {
  return useQuery<PaginatedResponse<Document>>({
    queryKey: ["documents", params],
    queryFn: () => api.documents.list(params),
  });
}

export function useDocument(id: string) {
  return useQuery<Document>({
    queryKey: ["documents", id],
    queryFn: () => api.documents.get(id),
    enabled: !!id,
  });
}

export function useDocumentChunks(id: string) {
  return useQuery<Chunk[]>({
    queryKey: ["documents", id, "chunks"],
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
  return useQuery<ModelInfo[]>({
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

export function useWatcherFiles(params?: PaginationParams) {
  return useQuery<PaginatedResponse<WatchedFile>>({
    queryKey: ["watcher", "files", params],
    queryFn: () => api.watcher.files(params),
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
  return useQuery<PaginatedResponse<EvaluationDataset>>({
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
    mutationFn: (formData: FormData) => api.evaluation.datasets.create(formData),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["evaluation", "datasets"] });
    },
  });
}

export function useEvaluationRuns() {
  return useQuery<PaginatedResponse<EvaluationRun>>({
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
  return useQuery<PaginatedResponse<Trace>>({
    queryKey: ["monitoring", "traces", params],
    queryFn: () => api.monitoring.traces(params),
  });
}

export function useTraceDetail(id: string) {
  return useQuery<Trace>({
    queryKey: ["monitoring", "traces", id],
    queryFn: () => api.monitoring.traceDetail(id),
    enabled: !!id,
  });
}

export function useCosts(params?: { start_date?: string; end_date?: string }) {
  return useQuery<CostEntry[]>({
    queryKey: ["monitoring", "costs", params],
    queryFn: () => api.monitoring.costs(params),
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
