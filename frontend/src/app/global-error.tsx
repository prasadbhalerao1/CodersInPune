"use client";

import "./globals.css";

import { ErrorScreen } from "@/components/error-screen";

// The last resort: the root layout itself failed, so this page brings its own <html> and
// stylesheet. Fonts fall back to the system stack here.
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body>
        <ErrorScreen
          code="500"
          title="Relay hit an unexpected error"
          digest={error.digest}
          onRetry={reset}
          full
        >
          The page could not be put together. Your data is safe; try again, and quote the reference
          below if it keeps happening.
        </ErrorScreen>
      </body>
    </html>
  );
}
