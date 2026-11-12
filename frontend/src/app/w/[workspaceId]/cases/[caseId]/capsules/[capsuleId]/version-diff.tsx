import { Minus, Plus } from "lucide-react";
import Link from "next/link";

import type { CapsuleView } from "@/lib/types";

type Change = { heading: string; text: string; added: boolean };

// Statement-level comparison of two brief versions, section by section. A reworded
// statement shows as one removal and one addition, which is what a reviewer must re-check.
function changes(from: CapsuleView, to: CapsuleView): Change[] {
  const texts = (c: CapsuleView, heading: string) =>
    new Set(c.sections.find((s) => s.heading === heading)?.points.map((p) => p.text) ?? []);
  const headings = [...new Set([...to.sections, ...from.sections].map((s) => s.heading))];
  return headings.flatMap((heading) => {
    const before = texts(from, heading);
    const after = texts(to, heading);
    return [
      ...[...before].filter((t) => !after.has(t)).map((text) => ({ heading, text, added: false })),
      ...[...after].filter((t) => !before.has(t)).map((text) => ({ heading, text, added: true })),
    ];
  });
}

export function VersionDiff({
  from,
  to,
  closeHref,
}: {
  from: CapsuleView;
  to: CapsuleView;
  closeHref: string;
}) {
  const list = changes(from, to);
  const summaryChanged = (from.summary ?? "") !== (to.summary ?? "");
  return (
    <section
      aria-labelledby="version-diff"
      className="motion-page bg-card flex flex-col gap-3 rounded-lg border p-4 shadow-xs"
    >
      <header className="flex items-center gap-2">
        <h2 id="version-diff" className="text-sm font-semibold">
          Changes from v{from.version} to v{to.version}
        </h2>
        <span className="text-muted-foreground text-xs">
          {list.filter((c) => c.added).length} added · {list.filter((c) => !c.added).length} removed
          {summaryChanged ? " · summary changed" : ""}
        </span>
        <Link href={closeHref} className="text-primary ml-auto text-xs font-medium hover:underline">
          Close comparison
        </Link>
      </header>
      {list.length === 0 ? (
        <p className="text-muted-foreground text-sm">
          No statement changed{summaryChanged ? "; only the summary was edited" : ""}.
        </p>
      ) : (
        <ul className="divide-y rounded-md border text-sm">
          {list.map((c) => (
            <li
              key={`${c.heading}:${c.added}:${c.text}`}
              className={
                c.added
                  ? "flex gap-2 bg-emerald-50/60 px-3 py-2 dark:bg-emerald-950/20"
                  : "flex gap-2 bg-red-50/60 px-3 py-2 dark:bg-red-950/20"
              }
            >
              {c.added ? (
                <Plus aria-label="Added" className="mt-0.5 size-4 shrink-0 text-emerald-700" />
              ) : (
                <Minus aria-label="Removed" className="mt-0.5 size-4 shrink-0 text-red-700" />
              )}
              <span className="min-w-0">
                <span className="text-muted-foreground block text-xs">{c.heading}</span>
                <span className={c.added ? undefined : "line-through decoration-red-700/40"}>
                  {c.text}
                </span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
