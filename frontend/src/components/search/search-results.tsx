"use client";

import { Badge } from "@/components/ui/badge";
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
      {data.cache_hit !== undefined && (
        <div className="flex items-center gap-2">
          <Badge variant={data.cache_hit ? "default" : "secondary"}>
            {data.cache_hit ? "캐시 HIT" : "캐시 MISS"}
          </Badge>
        </div>
      )}
      {data.pipeline_trace && data.pipeline_trace.length > 0 && (
        <PipelineTraceView steps={data.pipeline_trace} />
      )}
      <AnswerView answer={data.answer} results={data.results} />
    </div>
  );
}
