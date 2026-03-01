"use client";

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ArrowLeft, Play } from "lucide-react";
import {
  useEvaluationRuns,
  useEvaluationDatasets,
  useRunEvaluation,
  useEvaluationRun,
} from "@/lib/queries";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

function RunDetailDialog({
  runId,
  open,
  onOpenChange,
}: {
  runId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { data: run } = useEvaluationRun(runId);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[80vh] overflow-auto">
        <DialogHeader>
          <DialogTitle>평가 결과 상세</DialogTitle>
        </DialogHeader>
        {run ? (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-xs text-muted-foreground">Faithfulness</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-lg font-bold">{(run.metrics.faithfulness * 100).toFixed(1)}%</p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-xs text-muted-foreground">Relevancy</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-lg font-bold">{(run.metrics.answer_relevancy * 100).toFixed(1)}%</p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-xs text-muted-foreground">Precision</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-lg font-bold">{(run.metrics.context_precision * 100).toFixed(1)}%</p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-xs text-muted-foreground">Recall</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-lg font-bold">{(run.metrics.context_recall * 100).toFixed(1)}%</p>
                </CardContent>
              </Card>
            </div>

            {run.per_question_results?.length > 0 && (
              <div className="rounded-md border">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>질문</TableHead>
                      <TableHead className="text-right">Faith.</TableHead>
                      <TableHead className="text-right">Relev.</TableHead>
                      <TableHead className="text-right">Prec.</TableHead>
                      <TableHead className="text-right">Recall</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {run.per_question_results.map((r, i) => (
                      <TableRow key={i}>
                        <TableCell className="max-w-[300px] truncate">{r.question}</TableCell>
                        <TableCell className="text-right">{(r.faithfulness * 100).toFixed(1)}</TableCell>
                        <TableCell className="text-right">{(r.answer_relevancy * 100).toFixed(1)}</TableCell>
                        <TableCell className="text-right">{(r.context_precision * 100).toFixed(1)}</TableCell>
                        <TableCell className="text-right">{(r.context_recall * 100).toFixed(1)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </div>
        ) : (
          <p className="text-muted-foreground">로딩 중...</p>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default function RunsPage() {
  const { data: runsData, isLoading: runsLoading } = useEvaluationRuns();
  const { data: datasetsData } = useEvaluationDatasets();
  const runMutation = useRunEvaluation();
  const [selectedDataset, setSelectedDataset] = useState<string>("");
  const [detailRunId, setDetailRunId] = useState<string | null>(null);

  const handleRun = async () => {
    if (!selectedDataset) return;
    try {
      await runMutation.mutateAsync(selectedDataset);
      toast.success("평가 실행이 시작되었습니다.");
    } catch {
      toast.error("평가 실행에 실패했습니다.");
    }
  };

  const statusBadge = (status: string) => {
    switch (status) {
      case "completed":
        return <Badge variant="default">완료</Badge>;
      case "running":
        return <Badge variant="secondary">실행 중</Badge>;
      case "failed":
        return <Badge variant="destructive">실패</Badge>;
      default:
        return <Badge variant="outline">대기</Badge>;
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/evaluation">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <h2 className="text-2xl font-bold">평가 실행</h2>
      </div>

      {/* Run evaluation */}
      <div className="flex items-end gap-3">
        <div className="flex-1 space-y-1">
          <p className="text-sm font-medium">데이터셋 선택</p>
          <Select value={selectedDataset} onValueChange={setSelectedDataset}>
            <SelectTrigger>
              <SelectValue placeholder="데이터셋을 선택하세요" />
            </SelectTrigger>
            <SelectContent>
              {datasetsData?.items?.map((ds) => (
                <SelectItem key={ds.id} value={ds.id}>
                  {ds.name} ({ds.qa_count} QA)
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <Button onClick={handleRun} disabled={!selectedDataset || runMutation.isPending}>
          <Play className="mr-2 h-4 w-4" />
          {runMutation.isPending ? "실행 중..." : "평가 실행"}
        </Button>
      </div>

      {/* Runs table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>실행일</TableHead>
              <TableHead>데이터셋</TableHead>
              <TableHead>상태</TableHead>
              <TableHead className="text-right">Faith.</TableHead>
              <TableHead className="text-right">Relev.</TableHead>
              <TableHead className="text-right">Prec.</TableHead>
              <TableHead className="text-right">Recall</TableHead>
              <TableHead className="text-right">작업</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {runsLoading ? (
              <TableRow>
                <TableCell colSpan={8} className="h-24 text-center">
                  로딩 중...
                </TableCell>
              </TableRow>
            ) : !runsData?.items?.length ? (
              <TableRow>
                <TableCell colSpan={8} className="h-24 text-center">
                  평가 실행 기록이 없습니다.
                </TableCell>
              </TableRow>
            ) : (
              runsData.items.map((run) => (
                <TableRow key={run.id}>
                  <TableCell>
                    {new Date(run.created_at).toLocaleDateString("ko-KR")}
                  </TableCell>
                  <TableCell>{run.dataset_name || run.dataset_id}</TableCell>
                  <TableCell>{statusBadge(run.status)}</TableCell>
                  <TableCell className="text-right">
                    {run.metrics ? (run.metrics.faithfulness * 100).toFixed(1) : "-"}
                  </TableCell>
                  <TableCell className="text-right">
                    {run.metrics ? (run.metrics.answer_relevancy * 100).toFixed(1) : "-"}
                  </TableCell>
                  <TableCell className="text-right">
                    {run.metrics ? (run.metrics.context_precision * 100).toFixed(1) : "-"}
                  </TableCell>
                  <TableCell className="text-right">
                    {run.metrics ? (run.metrics.context_recall * 100).toFixed(1) : "-"}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setDetailRunId(run.id)}
                      disabled={run.status !== "completed"}
                    >
                      상세
                    </Button>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {detailRunId && (
        <RunDetailDialog
          runId={detailRunId}
          open={!!detailRunId}
          onOpenChange={(open) => !open && setDetailRunId(null)}
        />
      )}
    </div>
  );
}
