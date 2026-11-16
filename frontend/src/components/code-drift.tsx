import { GitPullRequest } from "lucide-react";
import Link from "next/link";

import { Explain } from "@/components/explain";
import { formatDateTime } from "@/components/page";
import type { DriftItem } from "@/lib/types";

/** Knowledge whose code changed after it was last reviewed, with the merges as evidence. */
export function CodeDrift({ items, workspaceId }: { items: DriftItem[]; workspaceId: string }) {
  if (!items.length) return null;
  return (
    <section
      aria-labelledby="code-drift"
      className="rounded-lg border border-amber-500/30 bg-amber-50/50 p-4 dark:bg-amber-950/20"
    >
      <h2 id="code-drift" className="flex items-center gap-2 font-semibold">
        <GitPullRequest aria-hidden className="size-4 text-amber-600" />
        Code changed since review ({items.length})
        <Explain what="code_drift" align="start" />
      </h2>
      <p className="text-muted-foreground mt-1 text-sm">
        Pull requests were merged into these responsibilities&apos; repositories after the knowledge
        was last checked. It may still be right; re-verify it.
      </p>
      <ul className="mt-3 flex flex-col gap-2">
        {items.slice(0, 8).map((d) => (
          <li key={d.knowledge_id} className="bg-card rounded-md border px-3 py-2 text-sm">
            <div className="flex flex-wrap items-baseline gap-x-2">
              <Link
                href={`/w/${workspaceId}/knowledge/${d.knowledge_id}`}
                className="font-medium hover:underline"
              >
                {d.title}
              </Link>
              <span className="text-muted-foreground text-xs">
                {d.responsibility_name} · checked {formatDateTime(d.checked_at)} · {d.merged_since}{" "}
                merge{d.merged_since === 1 ? "" : "s"} since
              </span>
            </div>
            <ul className="text-muted-foreground mt-1 flex flex-col gap-0.5 text-xs">
              {d.latest.map((c) => (
                <li key={c.url}>
                  <a href={c.url} className="hover:text-foreground hover:underline">
                    {c.repository}#{c.number} {c.title}
                  </a>{" "}
                  · merged {formatDateTime(c.merged_at)}
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ul>
    </section>
  );
}
