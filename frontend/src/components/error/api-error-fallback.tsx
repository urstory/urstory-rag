"use client";

import { ErrorState } from "./state";

interface Props {
  error: Error;
  retry?: () => void;
}

export function ApiErrorFallback({ error, retry }: Props) {
  return <ErrorState error={error} retry={retry} />;
}
