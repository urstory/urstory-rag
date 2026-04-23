"use client";

import React from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Props {
  children: React.ReactNode;
  fallback?: (error: Error, reset: () => void) => React.ReactNode;
  onError?: (error: Error, info: React.ErrorInfo) => void;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends React.Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("ErrorBoundary caught:", error, info);
    this.props.onError?.(error, info);
  }

  reset = () => this.setState({ error: null });

  render() {
    if (this.state.error) {
      if (this.props.fallback) {
        return this.props.fallback(this.state.error, this.reset);
      }
      return <ErrorBoundaryFallback error={this.state.error} reset={this.reset} />;
    }
    return this.props.children;
  }
}

function ErrorBoundaryFallback({
  error,
  reset,
}: {
  error: Error;
  reset: () => void;
}) {
  return (
    <div
      role="alert"
      aria-live="assertive"
      className="flex min-h-[320px] flex-col items-center justify-center gap-4 rounded-lg border border-destructive/30 bg-destructive/5 p-8 text-center"
    >
      <AlertTriangle
        className="h-10 w-10 text-destructive"
        aria-hidden="true"
      />
      <div className="space-y-1">
        <h3 className="text-lg font-semibold">화면을 표시하는 중 오류가 발생했습니다</h3>
        <p className="text-sm text-muted-foreground">
          {error.message || "알 수 없는 오류"}
        </p>
      </div>
      <Button onClick={reset} variant="outline">
        <RefreshCw className="mr-2 h-4 w-4" aria-hidden="true" />
        다시 시도
      </Button>
    </div>
  );
}
