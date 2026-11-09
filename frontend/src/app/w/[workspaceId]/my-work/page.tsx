import type { Metadata } from "next";
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

export const metadata: Metadata = { title: "My Work" };

const FILTERS = [
  { key: "all", label: "All" },
  { key: "today", label: "Today" },
  { key: "upcoming", label: "Upcoming" },
  { key: "overdue", label: "Overdue" },
  { key: "approvals", label: "Approvals" },
  { key: "mentions", label: "Mentions" },
  { key: "reviews", label: "Knowledge reviews" },
  { key: "cases", label: "My cases" },
] as const;

type Filter = (typeof FILTERS)[number]["key"];

/** Which due-date bucket a task falls in, relative to the end of today. */
function bucket(dueAt: string | null, now: Date): "overdue" | "today" | "upcoming" {
  if (!dueAt) return "upcoming";
  const due = new Date(dueAt);
  if (due < now) return "overdue";
  const endOfDay = new Date(now);
  endOfDay.setHours(23, 59, 59, 999);
  return due <= endOfDay ? "today" : "upcoming";
}

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
  const { emergencies, approvals, attention, mentions, reviews } = work.data;
  const now = new Date();
  const base = `/w/${workspaceId}`;
  const show = (key: Filter) => filter === "all" || filter === key;
  const taskFilter = ["today", "upcoming", "overdue"].includes(filter);
  const tasks = work.data.tasks.filter((t) => !taskFilter || bucket(t.due_at, now) === filter);
  const showTasks = filter === "all" || taskFilter;
  const empty =
    work.data.tasks.length +
      approvals.length +
      attention.length +
      myFollowUps.length +
      mentions.length +
      reviews.length ===
    0;

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
            description="Tasks assigned to you, approvals you can give, mentions, knowledge due for review, automation follow-ups and cases you coordinate appear here."
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
        {showTasks && tasks.length > 0 ? (
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
        {(filter === "all" || filter === "upcoming") && myFollowUps.length > 0 ? (
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
        {showTasks && filter !== "all" && tasks.length === 0 ? (
          <p className="text-muted-foreground text-sm">
            No tasks {filter === "today" ? "due today" : filter}.
          </p>
        ) : null}
        {show("mentions") && mentions.length > 0 ? (
          <Section title="Mentions" description="Unread comments that mention you.">
            <ul className="divide-y rounded-lg border">
              {mentions.map((m) => (
                <li key={m.notification_id}>
                  <Link
                    href={`${base}/cases/${m.case_id}`}
                    className="hover:bg-muted/40 flex items-center gap-3 px-4 py-2.5 text-sm"
                  >
                    <span className="min-w-0 flex-1 truncate">
                      <span className="font-medium">{m.actor_name ?? "Someone"}</span> mentioned you
                      in {m.case_title}
                    </span>
                    <span className="text-muted-foreground text-xs">
                      {formatDateTime(m.created_at)}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </Section>
        ) : null}
        {show("reviews") && reviews.length > 0 ? (
          <Section
            title="Knowledge to review"
            description="Knowledge you wrote that is past the review interval. Confirm it's still accurate or update it."
          >
            <ul className="divide-y rounded-lg border">
              {reviews.map((r) => (
                <li key={r.knowledge_id}>
                  <Link
                    href={`${base}/responsibilities/${r.responsibility_id}`}
                    className="hover:bg-muted/40 flex items-center gap-3 px-4 py-2.5 text-sm"
                  >
                    <span className="min-w-0 flex-1 truncate font-medium">{r.title}</span>
                    <span className="text-muted-foreground text-xs">{r.responsibility_name}</span>
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
