import Link from "next/link";

import { ApiErrorNotice } from "@/components/api-error-notice";
import { EmptyState, formatDateTime, PageHeader, Section } from "@/components/page";
import { Badge, CaseStatusBadge } from "@/components/ui/badge";
import { attempt } from "@/lib/attempt";
import { api } from "@/lib/relay-api";
import type { CaseSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

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
  const work = await attempt(api.myWork(workspaceId));
  if (!work.ok) return <ApiErrorNotice error={work.error} />;
  const { tasks, approvals, attention } = work.data;
  const base = `/w/${workspaceId}`;
  const show = (key: (typeof FILTERS)[number]["key"]) => filter === "all" || filter === key;
  const empty = tasks.length + approvals.length + attention.length === 0;

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
                <span className="block truncate font-medium">{c.title}</span>
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
