import type { Metadata } from "next";
import Link from "next/link";

import { ActionForm, SubmitButton } from "@/components/action-form";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { HandoverBanner } from "@/components/handover-banner";
import { Filtered, FilterTabs } from "@/components/filter-tabs";
import { EmptyState, formatDateTime, PageHeader, Section } from "@/components/page";
import { Badge, CaseStatusBadge, EmergencyBadge } from "@/components/ui/badge";
import { attempt } from "@/lib/attempt";
import { api } from "@/lib/relay-api";
import type { CaseSummary, TaskView } from "@/lib/types";

import { completeFollowUpAction } from "../automations/actions";
import { ReviewItem } from "../cases/[caseId]/privacy";

export const metadata: Metadata = { title: "My Work" };

const FILTERS = [
  { key: "all", label: "All" },
  { key: "today", label: "Today" },
  { key: "upcoming", label: "Upcoming" },
  { key: "overdue", label: "Overdue" },
  { key: "input", label: "Needs my input" },
  { key: "blocked", label: "Blocked" },
  { key: "approvals", label: "Approvals" },
  { key: "mentions", label: "Mentions" },
  { key: "reviews", label: "Knowledge reviews" },
  { key: "cases", label: "My cases" },
  { key: "done", label: "Completed" },
] as const;

type Filter = (typeof FILTERS)[number]["key"];

const BUCKET = {
  today: { title: "Due today", empty: "Nothing due today" },
  upcoming: { title: "Upcoming", empty: "Nothing upcoming" },
  overdue: { title: "Overdue", empty: "Nothing overdue" },
} as const;

/** Which due-date bucket a task falls in, relative to the end of today. */
function bucket(dueAt: string | null, now: Date): "overdue" | "today" | "upcoming" {
  if (!dueAt) return "upcoming";
  const due = new Date(dueAt);
  if (due < now) return "overdue";
  const endOfDay = new Date(now);
  endOfDay.setHours(23, 59, 59, 999);
  return due <= endOfDay ? "today" : "upcoming";
}

function TaskRows({ tasks, base }: { tasks: TaskView[]; base: string }) {
  return (
    <ul className="divide-y rounded-lg border">
      {tasks.map((t) => (
        <li key={t.id}>
          <Link
            href={`${base}/cases/${t.case_id}/tasks/${t.id}`}
            className="hover:bg-muted/40 flex items-center gap-3 px-4 py-2.5 text-sm"
          >
            <span className="min-w-0 flex-1">
              <span className="block truncate font-medium">{t.title}</span>
              {t.case_title ? (
                <span className="text-muted-foreground block truncate text-xs">
                  {t.case_title}
                  {t.assignee_team_name ? ` · team ${t.assignee_team_name}` : ""}
                </span>
              ) : null}
            </span>
            {t.blocked_by.length && t.status === "open" ? (
              <Badge tone="muted">Waits for {t.blocked_by.join(", ")}</Badge>
            ) : null}
            {t.needs_input_from_name && t.status === "open" ? (
              <Badge tone="warning">Asked {t.needs_input_from_name}</Badge>
            ) : null}
            {t.overdue ? <Badge tone="danger">Overdue</Badge> : null}
            {t.status === "done" && t.completed_at ? (
              <span className="text-muted-foreground text-xs">
                Done {formatDateTime(t.completed_at)}
              </span>
            ) : t.due_at ? (
              <span className="text-muted-foreground text-xs">Due {formatDateTime(t.due_at)}</span>
            ) : null}
          </Link>
        </li>
      ))}
    </ul>
  );
}

export default async function MyWorkPage({
  params,
  searchParams,
}: PageProps<"/w/[workspaceId]/my-work">) {
  const [{ workspaceId }, query] = await Promise.all([params, searchParams]);
  const filter = FILTERS.find((f) => f.key === query.show)?.key ?? "all";
  const [work, followUps, inbox] = await Promise.all([
    attempt(api.myWork(workspaceId)),
    attempt(api.followUps(workspaceId)),
    attempt(api.reviewInbox(workspaceId)),
  ]);
  const toReview = inbox.ok ? inbox.data : [];
  if (!work.ok) return <ApiErrorNotice error={work.error} />;
  const myFollowUps = followUps.ok ? followUps.data : [];
  const { emergencies, approvals, attention, mentions, reviews } = work.data;
  const now = new Date();
  const base = `/w/${workspaceId}`;
  const all = work.data.tasks;
  const byBucket = (key: "today" | "upcoming" | "overdue") =>
    all.filter((t) => bucket(t.due_at, now) === key);
  const buckets = {
    today: byBucket("today"),
    upcoming: byBucket("upcoming"),
    overdue: byBucket("overdue"),
  };
  const blocked = all.filter((t) => t.blocked_by.length > 0);
  const { needs_input: asked, completed } = work.data;
  const counts: Partial<Record<Filter, number>> = {
    today: buckets.today.length,
    overdue: buckets.overdue.length,
    input: asked.length + toReview.length,
    blocked: blocked.length,
    approvals: approvals.length,
    mentions: mentions.length,
    reviews: reviews.length,
  };
  const empty =
    all.length +
      approvals.length +
      attention.length +
      myFollowUps.length +
      mentions.length +
      reviews.length +
      work.data.handovers.length +
      work.data.to_accept.length +
      asked.length +
      toReview.length ===
    0;

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader
        title="My Work"
        description="Everything waiting on you: handovers to read, tasks, approvals and questions."
      />
      <div className="flex flex-col gap-6 p-6">
        <HandoverBanner workspaceId={workspaceId} handovers={work.data.handovers} />
        {work.data.to_accept.length > 0 ? (
          <section
            aria-label="Work to accept"
            className="rounded-lg border border-emerald-600/25 bg-emerald-50/60 dark:bg-emerald-950/20"
          >
            <p className="px-4 pt-3 text-xs font-semibold text-emerald-900 dark:text-emerald-200">
              You are named as the incoming owner: accept to confirm you are taking this on
            </p>
            <ul className="divide-y divide-emerald-600/10">
              {work.data.to_accept.map((a) => (
                <li key={`${a.case_id}-${a.responsibility_id}`}>
                  <Link
                    href={`${base}/cases/${a.case_id}`}
                    className="flex items-center gap-3 px-4 py-2.5 text-sm transition-colors hover:bg-emerald-100/50 dark:hover:bg-emerald-950/30"
                  >
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium">{a.responsibility_name}</span>
                      <span className="text-muted-foreground block truncate text-xs">
                        {a.case_title}
                      </span>
                    </span>
                    <span className="text-primary shrink-0 text-xs font-medium">Review and accept</span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        ) : null}
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
        <FilterTabs filters={FILTERS.map((f) => ({ ...f, count: counts[f.key] }))} initial={filter}>
          <Filtered when={["all", "input"]}>
            {toReview.length > 0 ? (
              <Section
                title="Review what will be shared"
                description="You're handing over: check what each case will share and with whom."
              >
                <ul className="divide-y rounded-lg border">
                  {toReview.map((i) => (
                    <ReviewItem key={i.id} workspaceId={workspaceId} item={i} showCase />
                  ))}
                </ul>
              </Section>
            ) : null}
            {asked.length > 0 ? (
              <Section
                title="Needs my input"
                description="Someone asked you a question on these tasks. Your reply answers it."
              >
                <TaskRows tasks={asked} base={base} />
              </Section>
            ) : null}
          </Filtered>
          <Filtered when={["input"]}>
            {asked.length + toReview.length === 0 ? (
              <EmptyState
                title="No open questions"
                description="Nobody is waiting on an answer from you."
              />
            ) : null}
          </Filtered>
          <Filtered when={["all"]}>
            {all.length > 0 ? (
              <Section
                title="Tasks assigned to me"
                description="Assigned to you or to one of your teams."
              >
                <TaskRows tasks={all} base={base} />
              </Section>
            ) : null}
          </Filtered>
          {(["today", "upcoming", "overdue"] as const).map((key) => (
            <Filtered key={key} when={[key]}>
              {buckets[key].length > 0 ? (
                <Section
                  title={BUCKET[key].title}
                  description="Assigned to you or to one of your teams."
                >
                  <TaskRows tasks={buckets[key]} base={base} />
                </Section>
              ) : (
                <EmptyState
                  title={BUCKET[key].empty}
                  description="Tasks assigned to you or your teams appear here by due date."
                />
              )}
            </Filtered>
          ))}
          <Filtered when={["blocked"]}>
            {blocked.length ? (
              <Section
                title="Blocked"
                description="Your tasks that wait on other tasks before they can be completed."
              >
                <TaskRows tasks={blocked} base={base} />
              </Section>
            ) : (
              <EmptyState
                title="Nothing blocked"
                description="None of your open tasks waits on another task."
              />
            )}
          </Filtered>
          <Filtered when={["done"]}>
            {completed.length ? (
              <Section title="Completed" description="Tasks you completed most recently.">
                <TaskRows tasks={completed} base={base} />
              </Section>
            ) : (
              <EmptyState
                title="Nothing completed yet"
                description="Tasks you complete appear here."
              />
            )}
          </Filtered>
          <Filtered when={["all", "upcoming"]}>
            {myFollowUps.length > 0 ? (
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
          </Filtered>
          <Filtered when={["all", "mentions"]}>
            {mentions.length > 0 ? (
              <Section title="Mentions" description="Unread comments that mention you.">
                <ul className="divide-y rounded-lg border">
                  {mentions.map((m) => (
                    <li key={m.notification_id}>
                      <Link
                        href={`${base}/cases/${m.case_id}`}
                        className="hover:bg-muted/40 flex items-center gap-3 px-4 py-2.5 text-sm"
                      >
                        <span className="min-w-0 flex-1 truncate">
                          <span className="font-medium">{m.actor_name ?? "Someone"}</span> mentioned
                          you in {m.case_title}
                        </span>
                        <span className="text-muted-foreground text-xs">
                          {formatDateTime(m.created_at)}
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </Section>
            ) : (
              <Filtered when={["mentions"]}>
                <EmptyState
                  title="No unread mentions"
                  description="Comments that mention you appear here."
                />
              </Filtered>
            )}
          </Filtered>
          <Filtered when={["all", "reviews"]}>
            {reviews.length > 0 ? (
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
                        <span className="text-muted-foreground text-xs">
                          {r.responsibility_name}
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </Section>
            ) : (
              <Filtered when={["reviews"]}>
                <EmptyState
                  title="No knowledge due for review"
                  description="Knowledge you wrote appears here when it passes its review interval."
                />
              </Filtered>
            )}
          </Filtered>
          <Filtered when={["all", "approvals"]}>
            {approvals.length > 0 ? (
              <CaseList
                title="Waiting for my approval"
                cases={approvals}
                base={base}
                hint="Review the plan and approve"
              />
            ) : (
              <Filtered when={["approvals"]}>
                <EmptyState
                  title="Nothing to approve"
                  description="Case plans that need your sign-off appear here."
                />
              </Filtered>
            )}
          </Filtered>
          <Filtered when={["all", "cases"]}>
            {attention.length > 0 ? (
              <CaseList title="Cases I coordinate" cases={attention} base={base} />
            ) : (
              <Filtered when={["cases"]}>
                <EmptyState
                  title="No cases to coordinate"
                  description="Open cases you coordinate appear here."
                />
              </Filtered>
            )}
          </Filtered>
        </FilterTabs>
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
