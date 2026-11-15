"use client";

import { ErrorScreen } from "@/components/error-screen";

export default function WorkspacesError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <ErrorScreen
      code="503"
      title="Could not load your workspaces"
      digest={error.digest}
      onRetry={reset}
    >
      The workspace service may be starting up or the connection timed out. Nothing was changed.
    </ErrorScreen>
  );
}
