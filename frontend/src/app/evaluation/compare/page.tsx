"use client";

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ArrowLeft, GitCompare } from "lucide-react";
import { useEvaluationRuns, useCompareRuns } from "@/lib/queries";
import { cn } from "@/lib/utils";

export default function ComparePage() {
  const { data: runsData } = useEvaluationRuns();
  const [run1Id, setRun1Id] = useState("");
  const [run2Id, setRun2Id] = useState("");
  const { data: comparison, isLoading: comparing } = useCompareRuns(run1Id, run2Id);

  const completedRuns = (runsData?.items ?? []).filter((r) => r.status === "completed");

  const metricLabels: Record<string, string> = {
    faithfulness: "Faithfulness",
    answer_relevancy: "Answer Relevancy",
    context_precision: "Context Precision",
    context_recall: "Context Recall",
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/evaluation">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <h2 className="text-2xl font-bold">평가 비교</h2>
      </div>

      {/* Run selectors */}
      <div className="grid gap-4 grid-cols-1 sm:grid-cols-2">
        <div className="space-y-2">
          <p className="text-sm font-medium">실행 A</p>
          <Select value={run1Id} onValueChange={setRun1Id}>
            <SelectTrigger>
              <SelectValue placeholder="실행을 선택하세요" />
            </SelectTrigger>
            <SelectContent>
              {completedRuns.map((run) => (
                <SelectItem key={run.id} value={run.id}>
                  {new Date(run.created_at).toLocaleDateString("ko-KR")} - {run.dataset_name || run.dataset_id}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2">
          <p className="text-sm font-medium">실행 B</p>
          <Select value={run2Id} onValueChange={setRun2Id}>
            <SelectTrigger>
              <SelectValue placeholder="실행을 선택하세요" />
            </SelectTrigger>
            <SelectContent>
              {completedRuns.map((run) => (
                <SelectItem key={run.id} value={run.id}>
                  {new Date(run.created_at).toLocaleDateString("ko-KR")} - {run.dataset_name || run.dataset_id}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Comparison results */}
      {comparing && <p className="text-muted-foreground">비교 중...</p>}

      {comparison && (
        <div className="space-y-4">
          <div className="flex items-center gap-2">
            <GitCompare className="h-5 w-5" />
            <h3 className="text-lg font-semibold">메트릭 비교</h3>
          </div>
          <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">
            {(Object.keys(metricLabels) as Array<keyof typeof metricLabels>).map((metric) => {
              const val1 = comparison.run1.metrics[metric as keyof typeof comparison.run1.metrics];
              const val2 = comparison.run2.metrics[metric as keyof typeof comparison.run2.metrics];
              const diff = comparison.metric_diffs[metric as keyof typeof comparison.metric_diffs];
              const isPositive = diff > 0;

              return (
                <Card key={metric}>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-xs text-muted-foreground">
                      {metricLabels[metric]}
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span>A: {(val1 * 100).toFixed(1)}%</span>
                      <span>B: {(val2 * 100).toFixed(1)}%</span>
                    </div>
                    <Badge
                      variant="outline"
                      className={cn(
                        isPositive ? "text-green-600 border-green-200" : "text-red-600 border-red-200",
                      )}
                    >
                      {isPositive ? "+" : ""}{(diff * 100).toFixed(1)}%
                    </Badge>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>
      )}

      {!run1Id || !run2Id ? (
        <div className="flex h-32 items-center justify-center text-muted-foreground">
          비교할 두 개의 실행을 선택하세요.
        </div>
      ) : null}
    </div>
  );
}
