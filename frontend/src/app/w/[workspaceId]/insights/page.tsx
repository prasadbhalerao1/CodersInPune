import type { Metadata } from "next";
import Link from "next/link";

import { inputClass } from "@/components/action-form";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { formatDateTime, PageHeader, Section } from "@/components/page";
import { buttonVariants } from "@/components/ui/button";
import { attempt } from "@/lib/attempt";
import { api } from "@/lib/relay-api";
import type { DebtItem } from "@/lib/types";
import { cn } from "@/lib/utils";

export const metadata: Metadata = { title: "Insights" };

const CRITICALITY = ["critical", "high", "standard", "low"] as const;

function Stat({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div className="rounded-lg border px-4 py-3">
      <p className="text-muted-foreground text-xs">{label}</p>
      <p className="mt-1 text-xl font-semibold tabular-nums">{value}</p>
      {hint ? <p className="text-muted-foreground mt-0.5 text-xs">{hint}</p> : null}
    </div>
  );
}

const pct = (part: number, whole: number) => (whole ? `${Math.round((part / whole) * 100)}%` : "–");

function itemHref(workspaceId: string, item: DebtItem) {
  if (item.kind === "case") return `/w/${workspaceId}/cases/${item.id}`;
  if (item.kind === "person") return `/w/${workspaceId}/people/${item.id}`;
  return `/w/${workspaceId}/responsibilities/${item.id}`;
}

export default async function InsightsPage({
  params,
  searchParams,
}: PageProps<"/w/[workspaceId]/insights">) {
  const [{ workspaceId }, query] = await Promise.all([params, searchParams]);
  const department = typeof query.department_id === "string" ? query.department_id : undefined;
  const criticality = CRITICALITY.find((c) => c === query.criticality);
  const insights = await attempt(
    api.insights(workspaceId, { department_id: department, criticality }),
  );
  if (!insights.ok) return <ApiErrorNotice error={insights.error} />;
  const { coverage: c, knowledge: k, operations: o, debt, continuity_debt } = insights.data;

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader
        title="Insights"
        actions={
          <Link
            href={`/w/${workspaceId}/insights/trends`}
            className="text-sm underline-offset-2 hover:underline"
          >
            Trends →
          </Link>
        }
      />
      <div className="flex max-w-6xl flex-col gap-8 p-6">
        <form className="flex flex-wrap items-center gap-2" aria-label="Filters">
          <select
            name="department_id"
            defaultValue={department ?? ""}
            aria-label="Department"
            className={cn(inputClass, "h-9 w-48")}
          >
            <option value="">All departments</option>
            {insights.data.departments.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
          <select
            name="criticality"
            defaultValue={criticality ?? ""}
            aria-label="Criticality"
            className={cn(inputClass, "h-9 w-40")}
          >
            <option value="">Any criticality</option>
            {CRITICALITY.map((v) => (
              <option key={v} value={v}>
                {v[0].toUpperCase() + v.slice(1)}
              </option>
            ))}
          </select>
          <button type="submit" className={buttonVariants({ variant: "outline", size: "sm" })}>
            Apply
          </button>
          {department || criticality ? (
            <Link
              href={`/w/${workspaceId}/insights`}
              className="text-muted-foreground hover:text-foreground text-sm hover:underline"
            >
              Clear
            </Link>
          ) : null}
          <span className="text-muted-foreground ml-auto text-xs">
            Live as of {formatDateTime(insights.data.generated_at)}
          </span>
        </form>

        <Section
          title="Continuity Debt"
          description="The sum of the gaps below, each with its rule. Lower is better; fixing an item lowers the debt by its points."
        >
          <div className="grid gap-4 md:grid-cols-[12rem_1fr]">
            <div className="flex flex-col justify-center rounded-lg border px-5 py-4">
              <p className="text-muted-foreground text-xs">Continuity Debt</p>
              <p className="text-4xl font-semibold tabular-nums">{continuity_debt}</p>
              <p className="text-muted-foreground mt-1 text-xs">
                {o.accepted_risks
                  ? `${o.accepted_risks} accepted risk${o.accepted_risks === 1 ? "" : "s"} not counted`
                  : "No accepted risks excluded"}
              </p>
            </div>
            <ul className="divide-y rounded-lg border">
              {debt.map((component) => (
                <li key={component.key}>
                  <details className="group">
                    <summary className="hover:bg-muted/50 flex cursor-pointer list-none items-center gap-3 px-4 py-3 text-sm">
                      <span className="min-w-0 flex-1">
                        <span className="font-medium">{component.label}</span>
                        <span className="text-muted-foreground block text-xs">
                          {component.rule}
                        </span>
                      </span>
                      <span className="text-muted-foreground text-xs tabular-nums">
                        {component.count} item{component.count === 1 ? "" : "s"}
                      </span>
                      <span className="w-12 text-right font-semibold tabular-nums">
                        {component.points}
                      </span>
                    </summary>
                    {component.items.length ? (
                      <ul className="border-t px-4 py-2 text-sm">
                        {component.items.map((item, i) => (
                          <li key={`${item.id}-${i}`} className="flex items-center gap-3 py-1.5">
                            <Link
                              href={itemHref(workspaceId, item)}
                              className="min-w-0 flex-1 truncate hover:underline"
                            >
                              {item.label}
                              {item.detail ? (
                                <span className="text-muted-foreground"> · {item.detail}</span>
                              ) : null}
                            </Link>
                            <span className="text-muted-foreground text-xs tabular-nums">
                              +{item.points}
                            </span>
                          </li>
                        ))}
                        {component.count > component.items.length ? (
                          <li className="text-muted-foreground py-1.5 text-xs">
                            Showing the {component.items.length} largest of {component.count}.
                          </li>
                        ) : null}
                      </ul>
                    ) : (
                      <p className="text-muted-foreground border-t px-4 py-3 text-sm">
                        Nothing here. Nice.
                      </p>
                    )}
                  </details>
                </li>
              ))}
            </ul>
          </div>
        </Section>

        <Section
          title="Key-person exposure"
          description="People who are the only active holder of some work: if they were away tomorrow, it would have nobody. Teams count as shared cover."
        >
          {insights.data.key_people.length ? (
            <ul className="divide-y rounded-lg border text-sm">
              {insights.data.key_people.map((p) => (
                <li key={p.person_id} className="flex flex-wrap items-start gap-3 px-4 py-3">
                  <span className="min-w-0 flex-1">
                    <Link
                      href={`/w/${workspaceId}/people/${p.person_id}`}
                      className="font-medium hover:underline"
                    >
                      {p.name}
                    </Link>
                    <span className="text-muted-foreground block text-xs">
                      Only holder of {p.sole_total} responsibilit{p.sole_total === 1 ? "y" : "ies"}
                      {p.sole_critical ? `, ${p.sole_critical} critical or high` : ""}:{" "}
                      {p.responsibilities.map((r, i) => (
                        <span key={r.id}>
                          {i ? ", " : ""}
                          <Link href={itemHref(workspaceId, r)} className="hover:underline">
                            {r.label}
                          </Link>
                        </span>
                      ))}
                    </span>
                  </span>
                  <Link
                    href={`/w/${workspaceId}/simulator?person=${p.person_id}`}
                    className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
                  >
                    What if {p.name.split(" ")[0]} is away?
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-muted-foreground rounded-lg border p-4 text-sm">
              Every responsibility in this view has more than one holder or a team. Nobody is a
              single point of failure.
            </p>
          )}
        </Section>

        <Section title="Coverage" description="Who is accountable, and who steps in.">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Active responsibilities" value={c.responsibilities} />
            <Stat
              label="With a primary owner"
              value={pct(c.with_primary, c.responsibilities)}
              hint={`${c.with_primary} of ${c.responsibilities}`}
            />
            <Stat
              label="With a backup"
              value={pct(c.with_backup, c.responsibilities)}
              hint={`${c.with_backup} of ${c.responsibilities}`}
            />
            <Stat
              label="Critical with a backup"
              value={pct(c.critical_with_backup, c.critical)}
              hint={`${c.critical_with_backup} of ${c.critical}`}
            />
            <Stat
              label="Archived people still holding roles"
              value={c.archived_owner_assignments}
            />
            <Stat
              label="Single-person dependencies"
              value={c.single_person_dependencies}
              hint="People who alone cover 2+ responsibilities"
            />
          </div>
        </Section>

        <Section
          title="Knowledge health"
          description={`Knowledge counts as current when reviewed in the last ${k.review_interval_days} days.`}
          aside={
            <Link
              href={`/w/${workspaceId}/knowledge?freshness=stale`}
              className="text-muted-foreground hover:text-foreground text-sm hover:underline"
            >
              Review stale knowledge →
            </Link>
          }
        >
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat
              label="Responsibilities with knowledge"
              value={pct(k.responsibilities_with_knowledge, c.responsibilities)}
              hint={`${k.responsibilities_with_knowledge} of ${c.responsibilities}`}
            />
            <Stat label="Without any knowledge" value={k.responsibilities_missing_knowledge} />
            <Stat label="Only stale knowledge" value={k.responsibilities_only_stale} />
            <Stat
              label="Items needing review"
              value={k.stale_items}
              hint={
                k.imported_needing_review
                  ? `${k.imported_needing_review} imported, not yet reviewed`
                  : undefined
              }
            />
          </div>
        </Section>

        <Section title="Continuity operations" description="Cases, tasks and risk follow-through.">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat
              label="Open cases"
              value={o.open_cases}
              hint={o.emergency_cases ? `${o.emergency_cases} emergency` : undefined}
            />
            <Stat
              label="Overdue"
              value={o.overdue_cases + o.overdue_tasks}
              hint={`${o.overdue_cases} cases, ${o.overdue_tasks} tasks`}
            />
            <Stat
              label="Closed in 90 days"
              value={o.closed_last_90_days}
              hint={
                o.median_days_to_close !== null
                  ? `median ${o.median_days_to_close} days to close`
                  : undefined
              }
            />
            <Stat label="Risks resolved in 30 days" value={o.risks_resolved_last_30_days} />
          </div>
        </Section>
      </div>
    </div>
  );
}
