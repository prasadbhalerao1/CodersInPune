import { Check, CircleAlert, CircleDashed } from "lucide-react";
import Link from "next/link";

import type { CapsuleView, CoverageItem } from "@/lib/types";
import { cn } from "@/lib/utils";

const RANK = { critical: 0, high: 1, standard: 2, low: 3 } as const;

function state(i: CoverageItem) {
  if (i.cited > 0) return "cited" as const;
  return i.statements > 0 ? ("uncited" as const) : ("missing" as const);
}

const LABEL = {
  cited: "Backed by evidence",
  uncited: "Mentioned without a source",
  missing: "Not covered",
};

/** Which responsibilities in the case the brief actually says something cited about. */
export function BriefCoverage({
  capsule,
  interviewHref,
}: {
  capsule: CapsuleView;
  interviewHref: string;
}) {
  const items = [...capsule.coverage].sort(
    (a, b) => RANK[a.criticality] - RANK[b.criticality] || a.name.localeCompare(b.name),
  );
  if (items.length === 0) return null;
  const cited = items.filter((i) => state(i) === "cited").length;
  const gaps = items.filter((i) => state(i) !== "cited");
  const criticalGaps = gaps.filter((i) => i.criticality === "critical").length;
  return (
    <section
      aria-labelledby="brief-coverage"
      data-tour="brief-coverage"
      className="bg-card flex flex-col gap-3 rounded-lg border p-4 shadow-xs"
    >
      <header className="flex flex-wrap items-baseline gap-2">
        <h2 id="brief-coverage" className="text-sm font-semibold">
          Brief coverage
        </h2>
        <span className="text-muted-foreground text-xs">
          {cited} of {items.length} responsibilities backed by cited evidence
          {criticalGaps ? ` · ${criticalGaps} critical not covered` : ""}
        </span>
        <div
          aria-hidden
          className="bg-muted ml-auto h-1.5 w-28 overflow-hidden rounded-full"
          title={`${cited} of ${items.length}`}
        >
          <div
            className="bg-primary h-full"
            style={{ width: `${Math.round((cited / items.length) * 100)}%` }}
          />
        </div>
      </header>
      <ul className="grid gap-1.5 text-sm sm:grid-cols-2">
        {items.map((i) => {
          const s = state(i);
          const Icon = s === "cited" ? Check : s === "uncited" ? CircleDashed : CircleAlert;
          return (
            <li key={i.responsibility_id} className="flex items-start gap-2">
              <Icon
                aria-hidden
                className={cn(
                  "mt-0.5 size-4 shrink-0",
                  s === "cited" && "text-primary",
                  s === "uncited" && "text-amber-700 dark:text-amber-400",
                  s === "missing" &&
                    (i.criticality === "critical"
                      ? "text-red-700 dark:text-red-400"
                      : "text-muted-foreground"),
                )}
              />
              <span className="min-w-0">
                <span className="font-medium">{i.name}</span>{" "}
                <span className="text-muted-foreground text-xs">· {i.criticality}</span>
                <span className="text-muted-foreground block text-xs">
                  {LABEL[s]}
                  {i.statements ? ` · ${i.cited} of ${i.statements} statements cited` : ""}
                </span>
              </span>
            </li>
          );
        })}
      </ul>
      {gaps.length ? (
        <p className="text-muted-foreground text-xs">
          A statement counts when it names the responsibility; it is backed when it cites an active
          source. Close gaps by{" "}
          <Link href={interviewHref} className="text-primary font-medium hover:underline">
            asking the current owner in the handover interview
          </Link>{" "}
          or by adding knowledge to the responsibility, then regenerate the brief.
        </p>
      ) : (
        <p className="text-muted-foreground text-xs">
          Every responsibility in this handover is named by at least one cited statement.
        </p>
      )}
    </section>
  );
}
