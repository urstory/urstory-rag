"use client";

import { useEffect } from "react";
import { AlertTriangle, RefreshCw, Home } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function RouteError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("RouteError:", error);
  }, [error]);

  return (
    <div
      role="alert"
      aria-live="assertive"
      className="flex min-h-[60vh] flex-col items-center justify-center gap-4 p-8 text-center"
    >
      <AlertTriangle className="h-12 w-12 text-destructive" aria-hidden="true" />
      <div className="space-y-2">
        <h2 className="text-xl font-semibold">페이지를 불러오지 못했습니다</h2>
        <p className="text-sm text-muted-foreground">
          {error.message || "일시적인 오류일 수 있습니다. 잠시 후 다시 시도해 주세요."}
        </p>
      </div>
      <div className="flex gap-2">
        <Button onClick={reset} variant="default">
          <RefreshCw className="mr-2 h-4 w-4" aria-hidden="true" />
          다시 시도
        </Button>
        <Button asChild variant="outline">
          <Link href="/">
            <Home className="mr-2 h-4 w-4" aria-hidden="true" />
            대시보드로
          </Link>
        </Button>
      </div>
      {error.digest && (
        <p className="text-xs text-muted-foreground">
          오류 코드: <code className="font-mono">{error.digest}</code>
        </p>
      )}
    </div>
  );
}
