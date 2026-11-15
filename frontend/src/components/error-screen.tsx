import { ArrowLeft, RotateCcw } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { RelayMark } from "@/components/brand";
import { cn } from "@/lib/utils";

/**
 * Every error and not-found page in one voice: the status in the landing's serif, a plain
 * explanation, a way back, and (for failures) the reference that matches the server log.
 * `full` fills the window (root pages); otherwise it sits inside the app shell.
 */
export function ErrorScreen({
  code,
  title,
  children,
  digest,
  onRetry,
  home = { href: "/", label: "Back to Relay" },
  full = false,
}: {
  code: string;
  title: string;
  children: ReactNode;
  digest?: string;
  onRetry?: () => void;
  home?: { href: string; label: string };
  full?: boolean;
}) {
  return (
    <div
      className={cn(
        "error-screen relative flex flex-1 flex-col items-center justify-center overflow-hidden px-6 py-16 text-center",
        full && "bg-page text-strong min-h-svh",
      )}
    >
      <div aria-hidden className="error-screen-glow" />
      {full ? (
        <Link
          href="/"
          className="error-brand mark-link absolute top-6 left-6 flex items-center gap-2"
        >
          <RelayMark className="size-7" />
          <span className="text-[19px] font-semibold tracking-[-0.03em]">Relay</span>
        </Link>
      ) : null}
      <p className="error-code font-display text-ac text-[clamp(5.5rem,16vw,10rem)] leading-none italic">
        {code}
      </p>
      <h1 className="font-heading mt-4 text-2xl font-semibold">{title}</h1>
      <div className="text-muted-foreground mt-3 max-w-md text-sm leading-relaxed">{children}</div>
      <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
        {onRetry ? (
          <button type="button" onClick={onRetry} className="btn btn-primary">
            <RotateCcw className="size-4" aria-hidden />
            Try again
          </button>
        ) : null}
        <Link href={home.href} className={cn("btn", onRetry ? "btn-quiet" : "btn-primary")}>
          <ArrowLeft className="size-4" aria-hidden />
          {home.label}
        </Link>
      </div>
      {/* The digest is an opaque id that matches the server log entry; safe to show. */}
      {digest ? (
        <p className="text-muted-foreground mt-8 font-mono text-xs">Reference {digest}</p>
      ) : null}
    </div>
  );
}
