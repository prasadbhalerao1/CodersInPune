import { ArrowRight, Inbox } from "lucide-react";
import Link from "next/link";

import type { HandoverForMe } from "@/lib/types";

/** The first thing a recipient needs: handovers addressed to them, waiting to be read. */
export function HandoverBanner({
  workspaceId,
  handovers,
}: {
  workspaceId: string;
  handovers: HandoverForMe[];
}) {
  const waiting = handovers.filter((h) => h.status === "approved");
  if (waiting.length === 0) return null;
  return (
    <section
      aria-label="Handovers waiting for you"
      className="border-primary/25 bg-accent/60 flex flex-col gap-3 rounded-lg border p-4"
    >
      {waiting.map((h) => (
        <div key={h.capsule_id} className="flex flex-wrap items-center gap-3">
          <span className="bg-primary text-primary-foreground flex size-8 shrink-0 items-center justify-center rounded-md">
            <Inbox aria-hidden className="size-4" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold">A handover is waiting for you</p>
            <p className="text-muted-foreground truncate text-sm">
              {h.case_title} · version {h.version}, approved. Read it, ask it questions, then
              acknowledge it.
            </p>
          </div>
          <Link
            href={`/w/${workspaceId}/cases/${h.case_id}/capsules/${h.capsule_id}`}
            className="bg-primary text-primary-foreground hover:bg-primary/90 inline-flex h-8 items-center gap-1.5 rounded-md px-3 text-sm font-medium shadow-xs"
          >
            Open handover
            <ArrowRight aria-hidden className="size-3.5" />
          </Link>
        </div>
      ))}
    </section>
  );
}
