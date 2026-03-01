"use client";

import { Badge } from "@/components/ui/badge";

interface IndexingStatusProps {
  status: string;
}

const statusConfig: Record<string, { label: string; variant: "default" | "secondary" | "destructive" | "outline" }> = {
  pending: { label: "대기", variant: "outline" },
  processing: { label: "처리 중", variant: "secondary" },
  indexed: { label: "완료", variant: "default" },
  failed: { label: "실패", variant: "destructive" },
};

export function IndexingStatus({ status }: IndexingStatusProps) {
  const config = statusConfig[status] || { label: status, variant: "outline" as const };
  return (
    <Badge variant={config.variant}>
      {config.label}
    </Badge>
  );
}
