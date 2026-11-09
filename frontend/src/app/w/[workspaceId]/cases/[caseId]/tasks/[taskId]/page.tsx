import type { Metadata } from "next";
import Link from "next/link";

import {
  ActionForm,
  DateTimeInput,
  Field,
  inputClass,
  SubmitButton,
} from "@/components/action-form";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { formatDateTime, PageHeader, Section } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { attempt } from "@/lib/attempt";
import { api } from "@/lib/relay-api";
import type { TaskEventView } from "@/lib/types";
import { cn } from "@/lib/utils";

import { changeTaskAction, setTaskStatusAction, taskMessageAction } from "../../../actions";
import { PRIORITY_LABEL } from "../../../labels";
import { AssigneeSelect } from "../../tasks";

export const metadata: Metadata = { title: "Task" };

function describe(e: TaskEventView): string {
  switch (e.kind) {
    case "comment":
      return "commented";
    case "clarification_requested":
      return "asked for clarification";
    case "clarification_answered":
      return "answered";
    case "reassigned":
      return e.detail.to_name ? `reassigned it to ${e.detail.to_name}` : "reassigned it";
    case "due_changed":
      return e.detail.to_due
        ? `moved the due date to ${formatDateTime(e.detail.to_due)}`
        : "removed the due date";
    case "completed":
      return e.detail.bulk ? "completed it (bulk)" : "completed it";
    case "reopened":
      return "reopened it";
    case "cancelled":
      return "cancelled it";
  }
}

export default async function TaskPage({
  params,
}: PageProps<"/w/[workspaceId]/cases/[caseId]/tasks/[taskId]">) {
  const { workspaceId, caseId, taskId } = await params;
  const [detail, caseDetail, members, teams] = await Promise.all([
    attempt(api.caseTask(workspaceId, caseId, taskId)),
    attempt(api.getCase(workspaceId, caseId)),
    attempt(api.members(workspaceId)),
    attempt(api.listTeams(workspaceId)),
  ]);
  if (!detail.ok) return <ApiErrorNotice error={detail.error} />;
  if (!caseDetail.ok) return <ApiErrorNotice error={caseDetail.error} />;
  const { task: t, events, can_answer } = detail.data;
  const c = caseDetail.data;
  const manage = c.allowed_actions.includes("add_task");
  const open = t.status === "open";
  const memberList = members.ok ? members.data.filter((m) => m.status === "active") : [];
  const caseBase = `/w/${workspaceId}/cases/${caseId}`;
  const assigned = t.assignee_user_id
    ? `user:${t.assignee_user_id}`
    : t.assignee_team_id
      ? `team:${t.assignee_team_id}`
      : "";
  const byId = new Map(c.tasks.map((x) => [x.id, x]));

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader
        title={
          <span className="flex min-w-0 items-center gap-2">
            <Link
              href={`${caseBase}?tab=tasks`}
              className="text-muted-foreground hover:text-foreground truncate"
            >
              {c.title}
            </Link>
            <span className="text-muted-foreground">/</span>
            <span className="truncate">{t.title}</span>
          </span>
        }
      />
      <div className="grid gap-8 p-6 xl:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="flex min-w-0 flex-col gap-8">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={t.status === "done" ? "neutral" : "muted"}>
              {t.status === "done" ? "Done" : t.status === "open" ? "Open" : "Cancelled"}
            </Badge>
            {t.blocked_by.length && open ? (
              <Badge tone="muted">Waits for {t.blocked_by.join(", ")}</Badge>
            ) : null}
            {t.needs_input_from_name ? (
              <Badge tone="warning">Waiting for {t.needs_input_from_name}</Badge>
            ) : null}
            {t.overdue ? <Badge tone="danger">Overdue</Badge> : null}
          </div>
          {t.description ? <p className="text-sm whitespace-pre-line">{t.description}</p> : null}

          {open && !t.blocked_by.length ? (
            <ActionForm
              action={setTaskStatusAction.bind(null, workspaceId, caseId, t.id, "done")}
              className="rounded-lg border p-4"
            >
              <p className="text-sm font-medium">Complete with evidence</p>
              <textarea
                name="completion_note"
                rows={2}
                maxLength={4000}
                placeholder="What was done (optional)"
                aria-label="Completion note"
                className={cn(inputClass, "h-auto py-2")}
              />
              <input
                name="completion_url"
                type="url"
                placeholder="Link to proof: PR, doc, recording (optional)"
                aria-label="Evidence link"
                className={inputClass}
              />
              <SubmitButton size="sm" pendingLabel="Completing…">
                Mark done
              </SubmitButton>
            </ActionForm>
          ) : null}
          {t.status === "done" ? (
            <div className="rounded-lg border p-4 text-sm">
              <p className="font-medium">
                Completed {t.completed_at ? formatDateTime(t.completed_at) : ""}
              </p>
              {t.completion_note ? (
                <p className="mt-1 whitespace-pre-line">{t.completion_note}</p>
              ) : null}
              {t.completion_url ? (
                <a
                  href={t.completion_url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-1 block underline underline-offset-2"
                >
                  {t.completion_url}
                </a>
              ) : null}
              <details className="mt-2">
                <summary className="text-muted-foreground hover:text-foreground cursor-pointer text-xs">
                  Reopen…
                </summary>
                <ActionForm
                  action={setTaskStatusAction.bind(null, workspaceId, caseId, t.id, "open")}
                  className="mt-2"
                >
                  <input
                    name="reason"
                    required
                    maxLength={4000}
                    placeholder="Why it isn't done"
                    aria-label="Reason"
                    className={inputClass}
                  />
                  <SubmitButton size="sm" variant="outline" pendingLabel="…">
                    Reopen task
                  </SubmitButton>
                </ActionForm>
              </details>
            </div>
          ) : null}

          <Section
            title="Activity"
            description="Comments, questions and every change, oldest first."
          >
            {events.length ? (
              <ol className="flex flex-col gap-3 text-sm">
                {events.map((e, i) => (
                  <li
                    key={i}
                    className={cn(
                      e.kind === "comment" || e.kind.startsWith("clarification")
                        ? "rounded-lg border p-3"
                        : "text-muted-foreground px-3 text-xs",
                    )}
                  >
                    <p>
                      <span className="text-foreground font-medium">
                        {e.actor_name ?? "Someone"}
                      </span>{" "}
                      {describe(e)}
                      <span className="text-muted-foreground">
                        {" "}
                        · {formatDateTime(e.created_at)}
                      </span>
                    </p>
                    {e.body ? <p className="mt-1 whitespace-pre-line">{e.body}</p> : null}
                  </li>
                ))}
              </ol>
            ) : (
              <p className="text-muted-foreground text-sm">No activity yet.</p>
            )}
            {open ? (
              <ActionForm action={taskMessageAction.bind(null, workspaceId, caseId, t.id)}>
                <textarea
                  name="body"
                  rows={3}
                  maxLength={5000}
                  required
                  aria-label="Message"
                  placeholder={can_answer ? "Answer the question…" : "Comment or ask a question…"}
                  className={cn(inputClass, "h-auto py-2")}
                />
                {!can_answer ? (
                  <div className="flex flex-wrap items-center gap-3 text-sm">
                    <label className="flex items-center gap-1.5">
                      <input type="radio" name="kind" value="comment" defaultChecked /> Comment
                    </label>
                    <label className="flex items-center gap-1.5">
                      <input type="radio" name="kind" value="clarification" /> Ask for clarification
                      from
                    </label>
                    <select
                      name="ask_user_id"
                      defaultValue=""
                      aria-label="Who should answer"
                      className={cn(inputClass, "h-8 w-auto")}
                    >
                      <option value="">the assignee</option>
                      {memberList.map((m) => (
                        <option key={m.user_id} value={m.user_id}>
                          {m.name}
                        </option>
                      ))}
                    </select>
                  </div>
                ) : null}
                <SubmitButton size="sm" pendingLabel="Sending…">
                  {can_answer ? "Send answer" : "Send"}
                </SubmitButton>
              </ActionForm>
            ) : null}
          </Section>
        </div>

        <aside className="flex flex-col gap-6">
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 rounded-lg border p-4 text-sm">
            <dt className="text-muted-foreground">Assignee</dt>
            <dd>{t.assignee_name ?? t.assignee_team_name ?? "Unassigned"}</dd>
            <dt className="text-muted-foreground">Priority</dt>
            <dd>{PRIORITY_LABEL[t.priority]}</dd>
            <dt className="text-muted-foreground">Due</dt>
            <dd>{t.due_at ? formatDateTime(t.due_at) : "—"}</dd>
            <dt className="text-muted-foreground">Waits for</dt>
            <dd>
              {t.depends_on.length
                ? t.depends_on.map((id) => {
                    const dep = byId.get(id);
                    return dep ? (
                      <Link
                        key={id}
                        href={`${caseBase}/tasks/${id}`}
                        className="block underline-offset-2 hover:underline"
                      >
                        {dep.status === "done" ? "✓ " : ""}
                        {dep.title}
                      </Link>
                    ) : null;
                  })
                : "—"}
            </dd>
            <dt className="text-muted-foreground">External</dt>
            <dd>
              {t.external_url ? (
                <a
                  href={t.external_url}
                  target="_blank"
                  rel="noreferrer"
                  className="underline underline-offset-2"
                >
                  {t.external_provider} · {t.sync_status}
                </a>
              ) : (
                <span className="text-muted-foreground">Not mirrored</span>
              )}
            </dd>
          </dl>
          {manage && open ? (
            <ActionForm
              action={changeTaskAction.bind(null, workspaceId, caseId, t.id)}
              className="rounded-lg border p-4"
            >
              <p className="text-sm font-medium">Reassign or reschedule</p>
              <Field label="Assignee" htmlFor="change-assignee">
                <AssigneeSelect
                  id="change-assignee"
                  members={memberList}
                  teams={teams.ok ? teams.data : []}
                  defaultValue={assigned}
                />
              </Field>
              <Field label="Due" htmlFor="change-due">
                <DateTimeInput id="change-due" name="due_at" defaultValue={t.due_at} />
              </Field>
              <Field label="Priority" htmlFor="change-priority">
                <select
                  id="change-priority"
                  name="priority"
                  defaultValue={t.priority}
                  className={inputClass}
                >
                  {Object.entries(PRIORITY_LABEL).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Reason (needed when reassigning)" htmlFor="change-reason">
                <input id="change-reason" name="reason" maxLength={4000} className={inputClass} />
              </Field>
              <SubmitButton size="sm" variant="outline" pendingLabel="Saving…">
                Save changes
              </SubmitButton>
              <p className="text-muted-foreground text-xs">
                Every change is kept in the activity; reminders follow the new date.
              </p>
            </ActionForm>
          ) : null}
        </aside>
      </div>
    </div>
  );
}
