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
    <div data-testid="search-results" className="space-y-4">
      {data.pipeline_trace && data.pipeline_trace.length > 0 && (
        <PipelineTraceView steps={data.pipeline_trace} />
      )}
      <AnswerView answer={data.answer} results={data.results} />
    </div>
  );
}
