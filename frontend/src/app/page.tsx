"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useMonitoringStats, useSettings, useSystemStatus, useEvaluationRuns } from "@/lib/queries";
import { FileText, Layers, MessageSquare, Clock } from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";

export default function DashboardPage() {
  const { data: stats, isLoading: statsLoading } = useMonitoringStats();
  const { data: settings, isLoading: settingsLoading } = useSettings();
  const { data: systemStatus } = useSystemStatus();
  const { data: runsData } = useEvaluationRuns();

  const recentRuns = (runsData?.items ?? [])
    .filter((r) => r.status === "completed" && r.metrics)
    .slice(0, 5)
    .map((r) => ({
      name: new Date(r.created_at).toLocaleDateString("ko-KR", { month: "short", day: "numeric" }),
      faithfulness: +(r.metrics.faithfulness * 100).toFixed(1),
      relevancy: +(r.metrics.answer_relevancy * 100).toFixed(1),
      precision: +(r.metrics.context_precision * 100).toFixed(1),
      recall: +(r.metrics.context_recall * 100).toFixed(1),
    }));

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">대시보드</h2>

      {/* Stats cards */}
      <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-4">
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
        <Card>
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-sm font-medium">평균 응답 시간</CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {statsLoading ? "..." : `${(stats?.avg_response_time_ms ?? 0).toLocaleString()}ms`}
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 grid-cols-1 lg:grid-cols-2">
        {/* Active Settings */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">현재 활성 설정</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {settingsLoading ? (
              <p className="text-muted-foreground">로딩 중...</p>
            ) : settings ? (
              <>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">임베딩</span>
                  <span className="font-medium">{settings.embedding.model} ({settings.embedding.provider})</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">검색 모드</span>
                  <Badge variant="secondary">{settings.search.mode}</Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">리랭킹</span>
                  <Badge variant={settings.reranking.enabled ? "default" : "outline"}>
                    {settings.reranking.enabled ? "ON" : "OFF"}
                  </Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">HyDE</span>
                  <Badge variant={settings.hyde.enabled ? "default" : "outline"}>
                    {settings.hyde.enabled ? "ON" : "OFF"}
                  </Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">가드레일</span>
                  <div className="flex gap-1">
                    <Badge variant={settings.guardrails.pii_detection ? "default" : "outline"}>PII</Badge>
                    <Badge variant={settings.guardrails.injection_detection ? "default" : "outline"}>인젝션</Badge>
                    <Badge variant={settings.guardrails.hallucination_detection ? "default" : "outline"}>할루시네이션</Badge>
                  </div>
                </div>
              </>
            ) : (
              <p className="text-muted-foreground">설정을 불러올 수 없습니다.</p>
            )}
          </CardContent>
        </Card>

        {/* Component Connection Status */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">컴포넌트 연결 상태</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {systemStatus?.components?.map((comp) => (
              <div key={comp.name} className="flex items-center justify-between">
                <span className="text-muted-foreground">{comp.name}</span>
                <Badge
                  variant={comp.status === "connected" ? "default" : "destructive"}
                >
                  {comp.status === "connected" ? "연결됨" : comp.status === "disconnected" ? "미연결" : "오류"}
                  {comp.latency_ms ? ` (${comp.latency_ms}ms)` : ""}
                </Badge>
              </div>
            )) ?? (
              <p className="text-muted-foreground">상태 정보를 불러올 수 없습니다.</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* RAGAS Score Chart */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">최근 RAGAS 점수 추이</CardTitle>
        </CardHeader>
        <CardContent>
          {recentRuns.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={recentRuns}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" fontSize={12} />
                <YAxis domain={[0, 100]} fontSize={12} />
                <Tooltip />
                <Legend />
                <Bar dataKey="faithfulness" name="Faithfulness" fill="hsl(220, 70%, 55%)" />
                <Bar dataKey="relevancy" name="Relevancy" fill="hsl(160, 60%, 45%)" />
                <Bar dataKey="precision" name="Precision" fill="hsl(40, 80%, 55%)" />
                <Bar dataKey="recall" name="Recall" fill="hsl(340, 65%, 50%)" />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-48 items-center justify-center text-muted-foreground">
              평가 실행 기록이 없습니다.
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
