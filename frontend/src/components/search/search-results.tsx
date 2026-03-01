"use client";

import { PipelineTraceView } from "./pipeline-trace";
import { AnswerView } from "./answer-view";
import type { DebugSearchResponse } from "@/types";

interface SearchResultsProps {
  data: DebugSearchResponse | null;
}

export function SearchResults({ data }: SearchResultsProps) {
  if (!data) return null;

  return (
    <div className="space-y-4">
      {data.pipeline_trace && (
        <PipelineTraceView trace={data.pipeline_trace} />
      )}
      <AnswerView answer={data.answer} documents={data.documents} />
    </div>
  );
}
