"use client";

import { useEffect, useState, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  RefreshCw,
} from "lucide-react";
import type { HealthCheck, ComponentHealth } from "@/types";
import { api } from "@/lib/api";

const IMPACT_MESSAGES: Record<string, string> = {
  database: "데이터베이스에 연결할 수 없습니다. 모든 기능이 제한됩니다.",
  elasticsearch: "검색 엔진에 연결할 수 없습니다. 키워드 검색이 비활성화됩니다.",
  redis: "캐시 서버에 연결할 수 없습니다. 로그인/로그아웃에 문제가 발생할 수 있습니다.",
  openai: "AI 서비스에 연결할 수 없습니다. 새 문서 임베딩과 답변 생성이 제한됩니다.",
};

function StatusIcon({ component }: { component: ComponentHealth }) {
  if (component.status === "connected") {
    return <CheckCircle2 className="h-5 w-5 text-green-500" />;
  }
  if (component.required) {
    return <XCircle className="h-5 w-5 text-red-500" />;
  }
  return <AlertTriangle className="h-5 w-5 text-amber-500" />;
}

function statusColor(component: ComponentHealth): string {
  if (component.status === "connected") return "border-green-200 bg-green-50";
  if (component.required) return "border-red-200 bg-red-50";
  return "border-amber-200 bg-amber-50";
}

export default function SystemStatusPage() {
  const [health, setHealth] = useState<HealthCheck | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);

  const fetchHealth = useCallback(async () => {
    try {
      const data = await api.system.health();
      setHealth(data);
      setLastChecked(new Date());
    } catch {
      setHealth(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 30000);
    return () => clearInterval(interval);
  }, [fetchHealth]);

  const handleRefresh = () => {
    setLoading(true);
    fetchHealth();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">시스템 상태</h2>
          <div className="flex items-center gap-3 mt-1">
            {health && (
              <>
                <Badge variant={health.status === "ok" ? "default" : "destructive"}>
                  {health.status === "ok" ? "정상" : "경고"}
                </Badge>
                <span className="text-sm text-muted-foreground">
                  v{health.version}
                </span>
              </>
            )}
            {lastChecked && (
              <span className="text-xs text-muted-foreground">
                마지막 확인: {lastChecked.toLocaleTimeString()}
              </span>
            )}
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={handleRefresh} disabled={loading}>
          <RefreshCw className={`h-4 w-4 mr-1 ${loading ? "animate-spin" : ""}`} />
          새로고침
        </Button>
      </div>

      {!health && !loading && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="pt-6 text-center">
            <p className="text-red-800 font-medium">
              서비스에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.
            </p>
          </CardContent>
        </Card>
      )}

      {health && (
        <div className="grid gap-4 grid-cols-1 sm:grid-cols-2">
          {Object.entries(health.components).map(([name, comp]) => (
            <Card key={name} className={statusColor(comp)}>
              <CardHeader className="flex flex-row items-center gap-3 pb-2">
                <StatusIcon component={comp} />
                <CardTitle className="text-sm capitalize">{name}</CardTitle>
                <Badge variant="outline" className="ml-auto text-xs">
                  {comp.required ? "필수" : "선택"}
                </Badge>
              </CardHeader>
              <CardContent className="space-y-1">
                <p className="text-xs text-muted-foreground">
                  {comp.description}
                </p>
                {comp.status === "disconnected" && (
                  <p className="text-xs font-medium text-red-700">
                    {IMPACT_MESSAGES[name] || comp.impact}
                  </p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <p className="text-xs text-muted-foreground text-center">
        30초마다 자동으로 상태를 확인합니다
      </p>
    </div>
  );
}
