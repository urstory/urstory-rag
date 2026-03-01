"use client";

import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useMonitoringStats, useTraces } from "@/lib/queries";
import { FileText, Layers, MessageSquare, List, BarChart3 } from "lucide-react";

export default function MonitoringPage() {
  const { data: stats, isLoading: statsLoading } = useMonitoringStats();
  const { data: tracesData, isLoading: tracesLoading } = useTraces({ page: 1, size: 10 });

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">모니터링</h2>

      {/* Quick links */}
      <div className="grid gap-4 grid-cols-1 sm:grid-cols-2">
        <Link href="/monitoring/traces">
          <Card className="cursor-pointer transition-colors hover:border-primary">
            <CardHeader className="flex flex-row items-center gap-3 pb-2">
              <List className="h-5 w-5 text-muted-foreground" />
              <CardTitle className="text-sm">트레이스</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-xs text-muted-foreground">요청별 상세 트레이스 확인</p>
            </CardContent>
          </Card>
        </Link>
        <Link href="/monitoring/metrics">
          <Card className="cursor-pointer transition-colors hover:border-primary">
            <CardHeader className="flex flex-row items-center gap-3 pb-2">
              <BarChart3 className="h-5 w-5 text-muted-foreground" />
              <CardTitle className="text-sm">시스템 메트릭</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-xs text-muted-foreground">응답 시간, 비용, 점수 분포</p>
            </CardContent>
          </Card>
        </Link>
      </div>

      {/* Stats */}
      <div className="grid gap-4 grid-cols-1 sm:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">총 문서</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {statsLoading ? "..." : (stats?.total_documents ?? 0).toLocaleString()}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">총 청크</CardTitle>
            <Layers className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {statsLoading ? "..." : (stats?.total_chunks ?? 0).toLocaleString()}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">오늘 쿼리</CardTitle>
            <MessageSquare className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {statsLoading ? "..." : (stats?.today_queries ?? 0).toLocaleString()}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Recent traces */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">최근 트레이스</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>시간</TableHead>
                <TableHead>쿼리</TableHead>
                <TableHead className="text-right">소요시간</TableHead>
                <TableHead className="text-right">상태</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {tracesLoading ? (
                <TableRow>
                  <TableCell colSpan={4} className="h-24 text-center">
                    로딩 중...
                  </TableCell>
                </TableRow>
              ) : !tracesData?.items?.length ? (
                <TableRow>
                  <TableCell colSpan={4} className="h-24 text-center">
                    트레이스가 없습니다.
                  </TableCell>
                </TableRow>
              ) : (
                tracesData.items.map((trace) => (
                  <TableRow key={trace.id}>
                    <TableCell className="text-xs text-muted-foreground">
                      {new Date(trace.created_at).toLocaleTimeString("ko-KR")}
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
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
