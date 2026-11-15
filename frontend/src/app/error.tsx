"use client";

import { ErrorScreen } from "@/components/error-screen";

export default function RootError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <ErrorScreen
      code="500"
      title="Something went wrong on our side"
      digest={error.digest}
      onRetry={reset}
      full
    >
      The service may be starting up or briefly unreachable. Your data is safe; try again in a
      moment, and quote the reference below if it keeps happening.
    </ErrorScreen>
  );
}
