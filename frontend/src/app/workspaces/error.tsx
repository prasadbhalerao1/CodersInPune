"use client";

import { RotateCcw } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function WorkspacesError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="bg-page text-strong flex flex-1 flex-col items-center justify-center gap-4 p-8 text-center">
      <div className="border-bad/30 bg-bad/10 text-bad grid size-12 place-items-center rounded-2xl border font-mono text-lg font-bold">
        !
      </div>
      <h2 className="font-syne text-xl font-bold tracking-tight">Could not load workspaces</h2>
      <p className="text-fg-soft max-w-md text-sm leading-relaxed">
        The workspace service may be starting up or the API connection timed out.
      </p>
      {error.digest ? (
        <p className="text-fg-mute font-mono text-xs">Digest: {error.digest}</p>
      ) : null}
      <div className="mt-2 flex items-center gap-3">
        <Button variant="outline" size="sm" onClick={reset} className="gap-2">
          <RotateCcw className="size-3.5" />
          Retry connection
        </Button>
        <Link
          href="/"
          className="border-line/15 text-fg-soft hover:text-strong rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors"
        >
          Back to home
        </Link>
      </div>
    </div>
  );
}
