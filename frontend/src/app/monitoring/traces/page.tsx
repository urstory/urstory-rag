"use client";

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ArrowLeft } from "lucide-react";
import { useTraces, useTraceDetail } from "@/lib/queries";
import type { PaginationParams } from "@/types";

function TraceDetailDialog({
  traceId,
  open,
  onOpenChange,
}: {
  traceId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { data: trace } = useTraceDetail(traceId);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[80vh] overflow-auto">
        <DialogHeader>
          <DialogTitle>트레이스 상세</DialogTitle>
        </DialogHeader>
        {trace ? (
          <div className="space-y-4">
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">쿼리</span>
                <span className="font-medium">{trace.query}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">총 소요시간</span>
                <span className="font-medium">{(trace.total_duration_ms / 1000).toFixed(2)}s</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">상태</span>
                <Badge variant={trace.status === "success" ? "default" : "destructive"}>
                  {trace.status === "success" ? "성공" : "오류"}
                </Badge>
              </div>
            </div>

            {/* Span timeline */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Span 타임라인</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {trace.spans?.map((span, i) => {
                    const widthPercent =
                      trace.total_duration_ms > 0
                        ? Math.max(5, (span.duration_ms / trace.total_duration_ms) * 100)
                        : 100;
                    return (
                      <div key={i} className="space-y-1">
                        <div className="flex items-center justify-between text-xs">
                          <span className="font-medium">{span.name}</span>
                          <span className="text-muted-foreground">{span.duration_ms}ms</span>
                        </div>
                        <div className="h-2 rounded-full bg-muted">
                          <div
                            className="h-2 rounded-full bg-primary"
                            style={{ width: `${widthPercent}%` }}
                          />
                        </div>
                      </div>
                    );
                  }) ?? (
                    <p className="text-xs text-muted-foreground">스팬 정보가 없습니다.</p>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        ) : (
          <p className="text-muted-foreground">로딩 중...</p>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default function TracesPage() {
  const [params, setParams] = useState<PaginationParams>({ page: 1, size: 20 });
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);
  const { data, isLoading } = useTraces(params);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/monitoring">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <h2 className="text-2xl font-bold">트레이스</h2>
      </div>

      <div className="rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>시간</TableHead>
              <TableHead>쿼리</TableHead>
              <TableHead className="text-right">소요시간</TableHead>
              <TableHead className="text-right">상태</TableHead>
              <TableHead className="text-right">작업</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={5} className="h-24 text-center">
                  로딩 중...
                </TableCell>
              </TableRow>
            ) : !data?.items?.length ? (
              <TableRow>
                <TableCell colSpan={5} className="h-24 text-center">
                  트레이스가 없습니다.
                </TableCell>
              </TableRow>
            ) : (
              data.items.map((trace) => (
                <TableRow key={trace.id}>
                  <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                    {new Date(trace.created_at).toLocaleString("ko-KR")}
                  </TableCell>
                  <TableCell className="max-w-[300px] truncate text-sm">
                    {trace.query}
                  </TableCell>
                  <TableCell className="text-right text-sm">
                    {(trace.total_duration_ms / 1000).toFixed(2)}s
                  </TableCell>
                  <TableCell className="text-right">
                    <Badge variant={trace.status === "success" ? "default" : "destructive"}>
                      {trace.status === "success" ? "성공" : "오류"}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setSelectedTraceId(trace.id)}
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

      {/* Total count */}
      {data && data.total > 0 && (
        <p className="text-sm text-muted-foreground">
          총 {data.total}개
        </p>
      )}

      {selectedTraceId && (
        <TraceDetailDialog
          traceId={selectedTraceId}
          open={!!selectedTraceId}
          onOpenChange={(open) => !open && setSelectedTraceId(null)}
        />
      )}
    </div>
  );
}
