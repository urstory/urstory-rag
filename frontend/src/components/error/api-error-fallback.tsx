"use client";

interface Props {
  error: Error;
  retry?: () => void;
}

export function ApiErrorFallback({ error, retry }: Props) {
  const requestId = (error as unknown as Record<string, unknown>).requestId as string | undefined;

  return (
    <div className="rounded-lg border border-red-200 bg-red-50 p-6 text-center space-y-3">
      <p className="font-medium text-red-800">
        {error.message || "요청을 처리하지 못했습니다."}
      </p>
      {retry && (
        <button
          onClick={retry}
          className="rounded-md bg-red-600 px-4 py-2 text-sm text-white hover:bg-red-700"
        >
          다시 시도
        </button>
      )}
      {requestId && (
        <p className="text-xs text-red-400">
          오류 코드: <code className="select-all">{requestId}</code>
        </p>
      )}
    </div>
  );
}
