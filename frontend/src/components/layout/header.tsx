"use client";

import { Menu } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useSystemStatus } from "@/lib/queries";

interface HeaderProps {
  onMenuToggle: () => void;
}

export function Header({ onMenuToggle }: HeaderProps) {
  const { data: systemStatus } = useSystemStatus();

  const statusColor = !systemStatus
    ? "bg-gray-400"
    : systemStatus.status === "ok"
      ? "bg-green-500"
      : systemStatus.status === "degraded"
        ? "bg-yellow-500"
        : "bg-red-500";

  const statusLabel = !systemStatus
    ? "확인 중"
    : systemStatus.status === "ok"
      ? "정상"
      : systemStatus.status === "degraded"
        ? "일부 장애"
        : "장애";

  return (
    <header className="flex h-14 items-center justify-between border-b px-4">
      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          size="icon"
          className="md:hidden"
          onClick={onMenuToggle}
        >
          <Menu className="h-5 w-5" />
        </Button>
        <span className="text-sm font-medium md:hidden">UrstoryRAG</span>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-xs text-muted-foreground">시스템 상태</span>
        <Badge variant="outline" className="gap-1.5">
          <span className={`h-2 w-2 rounded-full ${statusColor}`} />
          {statusLabel}
        </Badge>
      </div>
    </header>
  );
}
