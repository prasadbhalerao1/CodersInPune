import type { Metadata } from "next";
import Link from "next/link";

import { ApiErrorNotice } from "@/components/api-error-notice";
import { Explain } from "@/components/explain";
import { EmptyState, PageHeader } from "@/components/page";
import { CriticalityBadge } from "@/components/ui/badge";
import { attempt } from "@/lib/attempt";
import { api } from "@/lib/relay-api";
import type { ExpertiseMap } from "@/lib/types";
import { cn } from "@/lib/utils";

export const metadata: Metadata = { title: "Expertise map" };

const CELL = {
  primary: { label: "P", title: "Primary owner", className: "bg-primary text-primary-foreground" },
  backup: {
    label: "B",
    title: "Backup",
    className: "bg-sky-100 text-sky-900 dark:bg-sky-900/50 dark:text-sky-100",
  },
  knowledge: {
    label: "K",
    title: "Wrote its knowledge",
    className: "bg-emerald-100 text-emerald-900 dark:bg-emerald-900/50 dark:text-emerald-100",
  },
} as const;

function factorTone(n: number, criticality: string) {
  if (n <= 1 && (criticality === "critical" || criticality === "high"))
    return "bg-red-600 text-white";
  if (n <= 1) return "bg-amber-500 text-white";
  if (n === 2) return "bg-amber-100 text-amber-900 dark:bg-amber-900/50 dark:text-amber-100";
  return "bg-emerald-100 text-emerald-900 dark:bg-emerald-900/50 dark:text-emerald-100";
}

export default async function ExpertisePage({ params }: PageProps<"/w/[workspaceId]/expertise">) {
  const { workspaceId } = await params;
  const map = await attempt(api.expertise(workspaceId));
  if (!map.ok) return <ApiErrorNotice error={map.error} />;
  const { people, rows } = map.data;
  const base = `/w/${workspaceId}`;
  const single = rows.filter((r) => r.bus_factor <= 1).length;
  const namedOnly = rows.filter((r) => r.named_backup && !r.capable_backup).length;

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader
        title={
          <span className="flex items-center gap-2">
            Expertise map <Explain what="expertise" align="start" />
          </span>
        }
        description="Who could carry each responsibility tomorrow. The most fragile work is at the top."
      />
      <div className="flex min-w-0 flex-col gap-4 p-6">
        {rows.length === 0 ? (
          <EmptyState
            title="No responsibilities yet"
            description="Add responsibilities and their owners to see who holds what."
          />
        ) : (
          <>
            <div className="grid gap-3 sm:grid-cols-3">
              <Stat
                value={single}
                label="held by one person or nobody"
                tone="text-red-600"
                working={rows
                  .filter((r) => r.bus_factor <= 1)
                  .map((r) => `${r.name} (${r.criticality}): ${r.bus_factor}`)
                  .join("\n")}
              />
              <Stat
                value={namedOnly}
                label="with a backup on paper who never wrote anything down"
                tone="text-amber-600"
              />
              <Stat value={rows.length} label="responsibilities mapped" />
            </div>
            <Legend />
            <ExpertiseGrid people={people} rows={rows} base={base} />
          </>
        )}
      </div>
    </div>
  );
}

function Stat({
  value,
  label,
  tone,
  working,
}: {
  value: number;
  label: string;
  tone?: string;
  working?: string;
}) {
  return (
    <div className="bg-card rounded-lg border p-4">
      <p className={cn("text-3xl font-semibold tabular-nums", tone)}>{value}</p>
      <p className="text-muted-foreground mt-1 flex items-center gap-1 text-sm">
        {label}
        {working ? (
          <Explain
            what="expertise"
            align="start"
            working={<span className="whitespace-pre-line">{working}</span>}
          />
        ) : null}
      </p>
    </div>
  );
}

function Legend() {
  return (
    <p className="text-muted-foreground flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
      {Object.values(CELL).map((c) => (
        <span key={c.label} className="flex items-center gap-1.5">
          <span
            className={cn(
              "flex size-5 items-center justify-center rounded text-[10px] font-semibold",
              c.className,
            )}
          >
            {c.label}
          </span>
          {c.title}
        </span>
      ))}
      <span>Number = people who could carry it</span>
    </p>
  );
}

function ExpertiseGrid({
  people,
  rows,
  base,
}: ExpertiseMap & {
  base: string;
}) {
  return (
    <div className="bg-card overflow-auto rounded-lg border">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b">
            <th className="bg-card sticky left-0 z-10 min-w-56 px-3 py-2 text-left font-medium">
              Responsibility
            </th>
            <th className="px-2 py-2 font-medium" title="People who could carry it">
              People
            </th>
            <th className="px-2 py-2 text-left font-medium">Backup</th>
            {people.map((p) => (
              <th key={p.id} className="h-28 w-9 px-0 align-bottom font-normal">
                <Link
                  href={`${base}/people/${p.id}`}
                  className="text-muted-foreground hover:text-foreground mx-auto block w-5 rotate-180 truncate text-xs [writing-mode:vertical-rl]"
                >
                  {p.name}
                </Link>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.responsibility_id} className="hover:bg-muted/30 border-b last:border-0">
              <td className="bg-card sticky left-0 z-10 px-3 py-1.5">
                <span className="flex items-center gap-2">
                  <Link
                    href={`${base}/responsibilities/${r.responsibility_id}`}
                    className="min-w-0 truncate hover:underline"
                  >
                    {r.name}
                  </Link>
                  <CriticalityBadge value={r.criticality as "critical"} />
                </span>
              </td>
              <td className="px-2 py-1.5 text-center">
                <span
                  className={cn(
                    "inline-flex size-7 items-center justify-center rounded-full text-xs font-semibold tabular-nums",
                    factorTone(r.bus_factor, r.criticality),
                  )}
                >
                  {r.bus_factor}
                </span>
              </td>
              <td className="text-muted-foreground px-2 py-1.5 text-xs whitespace-nowrap">
                {r.capable_backup
                  ? "Capable"
                  : r.named_backup
                    ? "On paper only"
                    : r.team_covered
                      ? "Team"
                      : "None"}
              </td>
              {people.map((p) => {
                const kinds = r.cells[p.id] ?? [];
                return (
                  <td key={p.id} className="px-0.5 py-1.5 text-center">
                    {kinds.length ? (
                      <span
                        className="inline-flex gap-px"
                        title={`${p.name}: ${kinds.map((k) => CELL[k].title).join(", ")}`}
                      >
                        {kinds.map((k) => (
                          <span
                            key={k}
                            className={cn(
                              "flex size-5 items-center justify-center rounded text-[10px] font-semibold",
                              CELL[k].className,
                            )}
                          >
                            {CELL[k].label}
                          </span>
                        ))}
                      </span>
                    ) : null}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
