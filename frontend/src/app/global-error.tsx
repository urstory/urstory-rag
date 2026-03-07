"use client";

import { useEffect, useState } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const [errorId] = useState(
    () => error.digest || crypto.randomUUID().slice(0, 8),
  );

  useEffect(() => {
    console.error("GlobalError:", error);
  }, [error]);

  return (
    <html>
      <body className="flex min-h-screen items-center justify-center bg-gray-50 p-4">
        <div className="max-w-md text-center space-y-4">
          <h2 className="text-xl font-semibold text-gray-900">
            예상치 못한 오류가 발생했습니다
          </h2>
          <p className="text-gray-600">
            일시적인 문제일 수 있습니다. 아래 버튼을 눌러 다시 시도해 주세요.
          </p>
          <button
            onClick={reset}
            className="rounded-md bg-blue-600 px-4 py-2 text-white hover:bg-blue-700"
          >
            다시 시도
          </button>
          <div className="border-t pt-4 mt-4">
            <p className="text-sm text-gray-400">
              문제가 계속되면 관리자에게 아래 코드를 전달해 주세요.
            </p>
            <code className="text-sm font-mono text-gray-500 select-all">
              {errorId}
            </code>
          </div>
        </div>
      </body>
    </html>
  );
}
