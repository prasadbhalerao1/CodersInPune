import Link from "next/link";

import { ActionForm, SubmitButton } from "@/components/action-form";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { EmptyState, formatDateTime, PageHeader, Section } from "@/components/page";
import { Badge, CaseStatusBadge, EmergencyBadge } from "@/components/ui/badge";
import { attempt } from "@/lib/attempt";
import { api } from "@/lib/relay-api";
import type { CaseSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

import { completeFollowUpAction } from "../automations/actions";

const FILTERS = [
  { key: "all", label: "All" },
  { key: "tasks", label: "My tasks" },
  { key: "approvals", label: "Approvals" },
  { key: "cases", label: "My cases" },
] as const;

export default async function MyWorkPage({
  params,
  searchParams,
}: PageProps<"/w/[workspaceId]/my-work">) {
  const [{ workspaceId }, query] = await Promise.all([params, searchParams]);
  const filter = FILTERS.find((f) => f.key === query.show)?.key ?? "all";
  const [work, followUps] = await Promise.all([
    attempt(api.myWork(workspaceId)),
    attempt(api.followUps(workspaceId)),
  ]);
  if (!work.ok) return <ApiErrorNotice error={work.error} />;
  const myFollowUps = followUps.ok ? followUps.data : [];
  const { emergencies, tasks, approvals, attention } = work.data;
  const base = `/w/${workspaceId}`;
  const show = (key: (typeof FILTERS)[number]["key"]) => filter === "all" || filter === key;
  const empty = tasks.length + approvals.length + attention.length + myFollowUps.length === 0;

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader title="My Work" />
      <div className="flex flex-col gap-6 p-6">
        <nav aria-label="Filter" className="flex gap-1 text-sm">
          {FILTERS.map((f) => (
            <Link
              key={f.key}
              href={f.key === "all" ? `${base}/my-work` : `${base}/my-work?show=${f.key}`}
              aria-current={filter === f.key ? "page" : undefined}
              className={cn(
                "rounded-md px-2.5 py-1",
                filter === f.key
                  ? "bg-foreground/[0.06] font-medium"
                  : "text-muted-foreground hover:bg-muted",
              )}
            >
              {f.label}
            </Link>
          ))}
        </nav>
        {empty ? (
          <EmptyState
            title="You're all caught up"
            description="Tasks assigned to you, approvals you can give and cases you coordinate appear here."
          />
        ) : null}
        {emergencies.length > 0 ? (
          <section
            aria-label="Emergency cases"
            className="rounded-lg border border-red-600/25 bg-red-50/60 dark:bg-red-950/20"
          >
            <p className="px-4 pt-3 text-xs font-semibold text-red-900 dark:text-red-200">
              Emergency cases
            </p>
            <ul className="divide-y divide-red-600/10">
              {emergencies.map((c) => (
                <li key={c.id}>
                  <Link
                    href={`${base}/cases/${c.id}`}
                    className="flex items-center gap-3 px-4 py-2.5 text-sm hover:bg-red-100/50 dark:hover:bg-red-950/30"
                  >
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium">{c.title}</span>
                      <span className="text-muted-foreground block truncate text-xs">
                        {c.emergency_reason}
                      </span>
                    </span>
                    <CaseStatusBadge value={c.status} />
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        ) : null}
        {show("tasks") && tasks.length > 0 ? (
          <Section title="Tasks assigned to me" description="Complete them from the case.">
            <ul className="divide-y rounded-lg border">
              {tasks.map((t) => (
                <li key={t.id}>
                  <Link
                    href={`${base}/cases/${t.case_id}`}
                    className="hover:bg-muted/40 flex items-center gap-3 px-4 py-2.5 text-sm"
                  >
                    <span className="min-w-0 flex-1 truncate font-medium">{t.title}</span>
                    {t.overdue ? <Badge tone="danger">Overdue</Badge> : null}
                    {t.due_at ? (
                      <span className="text-muted-foreground text-xs">
                        Due {formatDateTime(t.due_at)}
                      </span>
                    ) : null}
                  </Link>
                </li>
              ))}
            </ul>
          </Section>
        ) : null}
        {show("tasks") && myFollowUps.length > 0 ? (
          <Section
            title="Follow-ups from automations"
            description="Fix the gap, then mark it done. A new follow-up opens if the gap remains."
          >
            <ul className="divide-y rounded-lg border">
              {myFollowUps.map((f) => (
                <li key={f.id} className="flex items-center gap-3 px-4 py-2.5 text-sm">
                  <Link
                    href={
                      f.case_id
                        ? `${base}/cases/${f.case_id}`
                        : `${base}/responsibilities/${f.responsibility_id}`
                    }
                    className="min-w-0 flex-1 truncate font-medium hover:underline"
                  >
                    {f.title}
                  </Link>
                  <span className="text-muted-foreground text-xs">
                    {formatDateTime(f.created_at)}
                  </span>
                  <ActionForm action={completeFollowUpAction.bind(null, workspaceId, f.id)}>
                    <SubmitButton size="sm" variant="outline" pendingLabel="…">
                      Done
                    </SubmitButton>
                  </ActionForm>
                </li>
              ))}
            </ul>
          </Section>
        ) : null}
        {show("approvals") && approvals.length > 0 ? (
          <CaseList
            title="Waiting for my approval"
            cases={approvals}
            base={base}
            hint="Review the plan and approve"
          />
        ) : null}
        {show("cases") && attention.length > 0 ? (
          <CaseList title="Cases I coordinate" cases={attention} base={base} />
        ) : null}
      </div>
    </div>
  );
}

function CaseList({
  title,
  cases,
  base,
  hint,
}: {
  title: string;
  cases: CaseSummary[];
  base: string;
  hint?: string;
}) {
  return (
    <Section title={title}>
      <ul className="divide-y rounded-lg border">
        {cases.map((c) => (
          <li key={c.id}>
            <Link
              href={`${base}/cases/${c.id}`}
              className="hover:bg-muted/40 flex items-center gap-3 px-4 py-2.5 text-sm"
            >
              <span className="min-w-0 flex-1">
                <span className="flex items-center gap-2">
                  <span className="truncate font-medium">{c.title}</span>
                  {c.emergency ? <EmergencyBadge /> : null}
                </span>
                <span className="text-muted-foreground text-xs">
                  {hint ?? `${c.open_tasks} open tasks`}
                  {c.overdue_tasks ? ` · ${c.overdue_tasks} overdue` : ""}
                </span>
              </span>
              <CaseStatusBadge value={c.status} />
            </Link>
          </li>
        ))}
      </ul>
    </Section>
  );
}
