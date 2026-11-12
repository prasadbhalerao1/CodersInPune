"use client";

import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";

/**
 * Live progress for a background AI run: every step with its state, a ticking timer, and
 * what happens next. Findings are validated against their citations before they are
 * stored, so they appear step by step (the page refreshes) rather than token by token.
 */
export function RunProgress({
  steps,
  step,
  queued,
  startedAt,
}: {
  steps: string[];
  step: number;
  queued: boolean;
  startedAt: string;
}) {
  const [now, setNow] = useState<number | null>(null);
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  const elapsed =
    now === null ? null : Math.max(0, Math.round((now - Date.parse(startedAt)) / 1000));
  return (
    <div className="flex flex-col gap-2" aria-live="polite">
      <p className="flex items-center gap-2 text-sm">
        <Spinner />
        <span className="font-medium">
          {queued ? "Waiting for a worker to pick this up…" : "Working through the evidence…"}
        </span>
        {elapsed !== null ? (
          <span className="text-muted-foreground text-xs tabular-nums">{elapsed}s</span>
        ) : null}
      </p>
      {steps.length ? (
        <ol className="flex flex-col gap-1.5 text-sm">
          {steps.map((name, i) => {
            const done = !queued && i < step;
            const current = !queued && i === step;
            return (
              <li
                key={name}
                className={cn(
                  "flex items-center gap-2",
                  !done && !current && "text-muted-foreground",
                )}
              >
                <span aria-hidden className="grid size-4 place-items-center">
                  {done ? (
                    <span className="text-xs">✓</span>
                  ) : current ? (
                    <Spinner small />
                  ) : (
                    <span className="bg-muted-foreground/40 size-1.5 rounded-full" />
                  )}
                </span>
                <span className={cn("capitalize", current && "font-medium")}>
                  {name.replaceAll("_", " ")}
                </span>
                {done ? <span className="text-muted-foreground text-xs">done</span> : null}
              </li>
            );
          })}
        </ol>
      ) : null}
      <p className="text-muted-foreground text-xs">
        Results appear below as each step finishes, after their citations are checked. You can leave
        this page; the run continues.
      </p>
    </div>
  );
}

function Spinner({ small = false }: { small?: boolean }) {
  return (
    <span
      aria-hidden
      className={cn(
        "border-muted-foreground/30 border-t-foreground inline-block animate-spin rounded-full border-2",
        small ? "size-3" : "size-4",
      )}
    />
  );
}

/** Placeholder rows where results will land while a run is in progress. */
export function PendingRows({ rows = 3, label }: { rows?: number; label: string }) {
  return (
    <div role="status" aria-label={label} className="flex flex-col gap-2 rounded-lg border p-4">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="flex flex-col gap-1.5">
          <div className="bg-muted h-3 w-1/3 animate-pulse rounded" />
          <div className="bg-muted/70 h-3 w-5/6 animate-pulse rounded" />
        </div>
      ))}
    </div>
  );
}
