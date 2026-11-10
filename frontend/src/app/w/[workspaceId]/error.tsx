"use client";

import { Button } from "@/components/ui/button";

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
    <div className="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center">
      <p className="font-medium">Relay couldn&apos;t load this page</p>
      <p className="text-muted-foreground max-w-sm text-sm">
        The service may be restarting or briefly unavailable. Try again in a moment.
      </p>
      {/* The digest is an opaque id that matches the server log entry; safe to show. */}
      {error.digest ? (
        <p className="text-muted-foreground font-mono text-xs">Reference: {error.digest}</p>
      ) : null}
      <Button variant="outline" size="sm" onClick={reset}>
        Try again
      </Button>
    </div>
  );
}
