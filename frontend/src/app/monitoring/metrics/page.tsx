"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ArrowLeft } from "lucide-react";
import { useMonitoringStats, useCosts } from "@/lib/queries";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  Legend,
} from "recharts";

export default function MetricsPage() {
  const { data: stats } = useMonitoringStats();
  const { data: costs } = useCosts();

  // Aggregate cost data from breakdown
  const costChartData = (costs?.breakdown ?? []).map((entry) => ({
    date: String(entry.date ?? ""),
    cost: Number(entry.cost ?? 0),
    tokens: Number(entry.tokens ?? 0),
  }));

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" asChild>
          <Link href="/monitoring">
            <ArrowLeft className="h-4 w-4" />
          </Link>
        </Button>
        <h2 className="text-2xl font-bold">시스템 메트릭</h2>
      </div>

      {/* Summary */}
      <div className="grid gap-4 grid-cols-1 sm:grid-cols-2">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">평균 응답 시간</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">
              {stats?.avg_response_time_ms ? `${stats.avg_response_time_ms.toLocaleString()}ms` : "-"}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">오늘 쿼리 수</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-bold">
              {stats?.today_queries?.toLocaleString() ?? "-"}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Cost chart */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">일별 비용 추이</CardTitle>
        </CardHeader>
        <CardContent>
          {costChartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={costChartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" fontSize={12} />
                <YAxis fontSize={12} />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="cost"
                  name="비용 (USD)"
                  stroke="hsl(220, 70%, 55%)"
                  strokeWidth={2}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-48 items-center justify-center text-muted-foreground">
              비용 데이터가 없습니다.
            </div>
          )}
        </CardContent>
      </Card>

      {/* Token usage chart */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">일별 토큰 사용량</CardTitle>
        </CardHeader>
        <CardContent>
          {costChartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={costChartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" fontSize={12} />
                <YAxis fontSize={12} />
                <Tooltip />
                <Legend />
                <Bar dataKey="tokens" name="토큰 수" fill="hsl(160, 60%, 45%)" />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-48 items-center justify-center text-muted-foreground">
              토큰 사용량 데이터가 없습니다.
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
