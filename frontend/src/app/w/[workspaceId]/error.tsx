"use client";

import { ErrorScreen } from "@/components/error-screen";

// Unexpected failures only (e.g. the API is unreachable). Expected API errors are rendered
// in place by ApiErrorNotice, and details never reach the browser in production.
export default function WorkspaceError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <ErrorScreen
      code="500"
      title="Relay couldn't load this page"
      digest={error.digest}
      onRetry={reset}
      home={{ href: "/workspaces", label: "Your workspaces" }}
    >
      The service may be restarting or briefly unavailable. Nothing was changed; try again in a
      moment.
    </ErrorScreen>
  );
}
