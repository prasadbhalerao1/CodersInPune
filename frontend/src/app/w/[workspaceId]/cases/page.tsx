import type { Metadata } from "next";
import Link from "next/link";

import { inputClass } from "@/components/action-form";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { PageNav } from "@/components/page-nav";
import { EmptyState, formatDateTime, PageHeader } from "@/components/page";
import { SavedViews } from "@/components/saved-views";
import { Badge, CaseStatusBadge, EmergencyBadge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { attempt } from "@/lib/attempt";
import { api, canManage } from "@/lib/relay-api";
import { cn } from "@/lib/utils";

import { CASE_TYPES, PRIORITY_LABEL, STATUS_LABEL } from "./labels";

export const metadata: Metadata = { title: "Continuity cases" };

const FILTERS = [
  "status",
  "priority",
  "case_type",
  "affected_person_id",
  "team_id",
  "overdue",
] as const;

export default async function CasesPage({
  params,
  searchParams,
}: PageProps<"/w/[workspaceId]/cases">) {
  const [{ workspaceId }, query] = await Promise.all([params, searchParams]);
  const filters: Record<string, string> = {};
  for (const key of FILTERS) {
    const value = query[key];
    if (typeof value === "string" && value) filters[key] = value;
  }
  const status = filters.status ?? "open";
  const after = typeof query.after === "string" ? query.after : undefined;
  const current = new URLSearchParams(filters).toString();
  const [workspace, cases, people, teams, views] = await Promise.all([
    attempt(api.getWorkspace(workspaceId)),
    attempt(api.listCases(workspaceId, { ...filters, status, after })),
    attempt(api.listPeople(workspaceId)),
    attempt(api.listTeams(workspaceId)),
    attempt(api.savedViews(workspaceId, "cases")),
  ]);
  if (!workspace.ok) return <ApiErrorNotice error={workspace.error} />;
  if (!cases.ok) return <ApiErrorNotice error={cases.error} />;
  const base = `/w/${workspaceId}/cases`;
  const manage = canManage(workspace.data);
  const filtered = Object.keys(filters).some((k) => k !== "status");

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader
        title="Cases"
        actions={
          manage ? (
            <Link href={`${base}/new`} className={buttonVariants({ size: "sm" })}>
              New case
            </Link>
          ) : (
            <Link
              href={`${base}/new?type=coverage&request=1`}
              className={buttonVariants({ size: "sm", variant: "outline" })}
            >
              Request cover
            </Link>
          )
        }
      />
      <div className="flex flex-col gap-4 p-6">
        <form
          method="get"
          action={base}
          className="flex flex-wrap items-end gap-2 text-sm"
          aria-label="Case filters"
        >
          <select
            name="status"
            defaultValue={status}
            aria-label="Status"
            className={cn(inputClass, "h-8 w-auto")}
          >
            <option value="open">All open</option>
            <option value="closed">Closed</option>
            {Object.entries(STATUS_LABEL).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <select
            name="priority"
            defaultValue={filters.priority ?? ""}
            aria-label="Priority"
            className={cn(inputClass, "h-8 w-auto")}
          >
            <option value="">Any priority</option>
            {Object.entries(PRIORITY_LABEL).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          <select
            name="case_type"
            defaultValue={filters.case_type ?? ""}
            aria-label="Case type"
            className={cn(inputClass, "h-8 w-auto")}
          >
            <option value="">Any type</option>
            {Object.entries(CASE_TYPES).map(([value, t]) => (
              <option key={value} value={value}>
                {t.label}
              </option>
            ))}
          </select>
          {people.ok ? (
            <select
              name="affected_person_id"
              defaultValue={filters.affected_person_id ?? ""}
              aria-label="Person affected"
              className={cn(inputClass, "h-8 w-auto")}
            >
              <option value="">Anyone</option>
              {people.data.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.display_name}
                </option>
              ))}
            </select>
          ) : null}
          {teams.ok ? (
            <select
              name="team_id"
              defaultValue={filters.team_id ?? ""}
              aria-label="Team"
              className={cn(inputClass, "h-8 w-auto")}
            >
              <option value="">Any team</option>
              {teams.data.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          ) : null}
          <label className="flex h-8 items-center gap-1.5 text-sm">
            <input
              type="checkbox"
              name="overdue"
              value="true"
              defaultChecked={filters.overdue === "true"}
            />
            Overdue
          </label>
          <Button type="submit" size="sm" variant="outline">
            Apply
          </Button>
          {filtered ? (
            <Link href={base} className="text-muted-foreground self-center text-xs hover:underline">
              Clear
            </Link>
          ) : null}
        </form>
        {views.ok ? (
          <SavedViews
            workspaceId={workspaceId}
            page="cases"
            base={base}
            views={views.data}
            current={current}
          />
        ) : null}
        {cases.data.length === 0 ? (
          <EmptyState
            title={
              filtered
                ? "No cases match these filters"
                : status === "closed"
                  ? "No closed cases yet"
                  : "No open cases"
            }
            description="Cases coordinate onboarding, transfers, coverage, departures and project handovers, with tasks, readiness checks and approvals."
            action={
              !filtered && status === "open" && manage ? (
                <Link href={`${base}/new`} className={buttonVariants({ size: "sm" })}>
                  Start a case
                </Link>
              ) : undefined
            }
          />
        ) : (
          <ul className="divide-y rounded-lg border">
            {cases.data.map((c) => (
              <li key={c.id}>
                <Link
                  href={`${base}/${c.id}`}
                  className="hover:bg-muted/40 grid grid-cols-[1fr_auto] items-center gap-4 px-4 py-3 text-sm sm:grid-cols-[minmax(0,1fr)_10rem_8rem_7rem]"
                >
                  <span className="min-w-0">
                    <span className="flex items-center gap-2">
                      <span className="truncate font-medium">{c.title}</span>
                      {c.emergency ? <EmergencyBadge /> : null}
                      {c.priority === "urgent" || c.priority === "high" ? (
                        <Badge tone={c.priority === "urgent" ? "danger" : "warning"}>
                          {PRIORITY_LABEL[c.priority]}
                        </Badge>
                      ) : null}
                    </span>
                    <span className="text-muted-foreground block truncate text-xs">
                      {CASE_TYPES[c.case_type].label}
                      {c.affected_person_name ? ` · ${c.affected_person_name}` : ""}
                      {` · ${c.scope_count} ${c.scope_count === 1 ? "responsibility" : "responsibilities"}`}
                      {c.parent_case_id ? " · split from a departure" : ""}
                    </span>
                  </span>
                  <span className="hidden sm:block">
                    <CaseStatusBadge value={c.status} />
                    {c.outcome === "completed_with_exceptions" ? (
                      <span className="text-muted-foreground ml-1 text-xs">· exceptions</span>
                    ) : null}
                  </span>
                  <span className="text-muted-foreground hidden text-xs sm:block">
                    {c.due_at ? `Due ${formatDateTime(c.due_at)}` : formatDateTime(c.starts_at)}
                  </span>
                  <span className="justify-self-end">
                    {c.overdue ? (
                      <Badge tone="danger">
                        {c.overdue_tasks > 0 ? `${c.overdue_tasks} overdue` : "Overdue"}
                      </Badge>
                    ) : c.open_tasks > 0 ? (
                      <span className="text-muted-foreground text-xs tabular-nums">
                        {c.open_tasks} open tasks
                      </span>
                    ) : null}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
        <PageNav base={base} query={filters} after={after} next={cases.data.nextCursor} />
      </div>
    </div>
  );
}
