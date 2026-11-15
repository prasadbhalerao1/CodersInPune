"use client";

import { RotateCcw } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function RootError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="bg-page text-strong flex min-h-svh flex-col items-center justify-center gap-4 p-6 text-center selection:bg-lime selection:text-cta-fg">
      <div className="size-12 rounded-2xl border border-bad/30 bg-bad/10 grid place-items-center font-mono text-lg font-bold text-bad">
        !
      </div>
      <h1 className="font-syne text-xl font-bold tracking-tight">Something unexpected happened</h1>
      <p className="text-fg-soft max-w-md text-sm leading-relaxed">
        The application encountered an issue. The backend service may be starting up or temporarily
        unreachable.
      </p>
      {error.digest ? (
        <p className="font-mono text-xs text-fg-mute">Error reference: {error.digest}</p>
      ) : null}
      <div className="mt-2 flex items-center gap-3">
        <Button variant="outline" size="sm" onClick={reset} className="gap-2">
          <RotateCcw className="size-3.5" />
          Try again
        </Button>
        <Link
          href="/"
          className="rounded-lg border border-line/15 px-3 py-1.5 text-xs font-medium text-fg-soft hover:text-strong transition-colors"
        >
          Return home
        </Link>
      </div>
    </div>
  );
}

