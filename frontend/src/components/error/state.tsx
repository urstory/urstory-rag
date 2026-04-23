"use client";

import { Loader2, AlertTriangle, Inbox, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";

interface LoadingStateProps {
  label?: string;
  className?: string;
}

export function LoadingState({ label = "불러오는 중...", className }: LoadingStateProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={
        className ??
        "flex min-h-[200px] flex-col items-center justify-center gap-3 text-muted-foreground"
      }
    >
      <Loader2 className="h-6 w-6 animate-spin" aria-hidden="true" />
      <span className="text-sm">{label}</span>
    </div>
  );
}

interface EmptyStateProps {
  title?: string;
  description?: string;
  action?: React.ReactNode;
  icon?: React.ReactNode;
  className?: string;
}

export function EmptyState({
  title = "데이터가 없습니다",
  description,
  action,
  icon,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={
        className ??
        "flex min-h-[200px] flex-col items-center justify-center gap-3 rounded-lg border border-dashed p-8 text-center"
      }
    >
      {icon ?? <Inbox className="h-8 w-8 text-muted-foreground" aria-hidden="true" />}
      <div className="space-y-1">
        <h3 className="text-sm font-medium">{title}</h3>
        {description && (
          <p className="text-xs text-muted-foreground">{description}</p>
        )}
      </div>
      {action}
    </div>
  );
}

interface ErrorStateProps {
  error: unknown;
  retry?: () => void;
  className?: string;
}

interface FriendlyError {
  title: string;
  description: string;
  actionLabel: string;
}

function describeError(error: unknown): FriendlyError {
  if (error instanceof ApiError) {
    switch (error.status) {
      case 401:
        return {
          title: "로그인이 필요합니다",
          description: "세션이 만료되었습니다. 다시 로그인해 주세요.",
          actionLabel: "로그인 페이지로",
        };
      case 403:
        return {
          title: "접근 권한이 없습니다",
          description: "이 작업을 수행할 권한이 없습니다. 관리자에게 문의하세요.",
          actionLabel: "다시 시도",
        };
      case 404:
        return {
          title: "요청한 리소스를 찾을 수 없습니다",
          description: error.message || "해당 항목이 삭제되었거나 이동되었을 수 있습니다.",
          actionLabel: "다시 시도",
        };
      case 429:
        return {
          title: "요청이 너무 많습니다",
          description: "잠시 후 다시 시도해 주세요.",
          actionLabel: "다시 시도",
        };
      case 500:
      case 502:
      case 503:
      case 504:
        return {
          title: "서버 오류가 발생했습니다",
          description: "일시적인 문제일 수 있습니다. 잠시 후 다시 시도해 주세요.",
          actionLabel: "다시 시도",
        };
      default:
        return {
          title: "요청을 처리하지 못했습니다",
          description: error.message || "잠시 후 다시 시도해 주세요.",
          actionLabel: "다시 시도",
        };
    }
  }

  // Native fetch errors (network offline, DNS, etc.) are TypeErrors like "Failed to fetch"
  if (error instanceof TypeError && /fetch/i.test(error.message)) {
    return {
      title: "서버에 연결할 수 없습니다",
      description: "네트워크 연결을 확인한 뒤 다시 시도해 주세요.",
      actionLabel: "다시 시도",
    };
  }

  if (error instanceof Error) {
    return {
      title: "오류가 발생했습니다",
      description: error.message,
      actionLabel: "다시 시도",
    };
  }

  return {
    title: "오류가 발생했습니다",
    description: "알 수 없는 오류입니다.",
    actionLabel: "다시 시도",
  };
}

export function ErrorState({ error, retry, className }: ErrorStateProps) {
  const { title, description, actionLabel } = describeError(error);

  return (
    <div
      role="alert"
      aria-live="assertive"
      className={
        className ??
        "flex min-h-[200px] flex-col items-center justify-center gap-3 rounded-lg border border-destructive/30 bg-destructive/5 p-6 text-center"
      }
    >
      <AlertTriangle className="h-8 w-8 text-destructive" aria-hidden="true" />
      <div className="space-y-1">
        <h3 className="text-sm font-semibold">{title}</h3>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
      {retry && (
        <Button onClick={retry} variant="outline" size="sm">
          <RefreshCw className="mr-2 h-4 w-4" aria-hidden="true" />
          {actionLabel}
        </Button>
      )}
    </div>
  );
}

/**
 * Pick the correct state component for a TanStack Query-style result.
 * Use when a page/section follows the simple (isLoading / isError / data) pattern.
 */
interface QueryStateProps<T> {
  isLoading: boolean;
  isError: boolean;
  error: unknown;
  data: T | undefined;
  retry?: () => void;
  empty?: EmptyStateProps;
  children: (data: T) => React.ReactNode;
}

export function QueryState<T>({
  isLoading,
  isError,
  error,
  data,
  retry,
  empty,
  children,
}: QueryStateProps<T>) {
  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState error={error} retry={retry} />;
  if (!data || (Array.isArray(data) && data.length === 0)) {
    return <EmptyState {...(empty ?? {})} />;
  }
  return <>{children(data)}</>;
}
