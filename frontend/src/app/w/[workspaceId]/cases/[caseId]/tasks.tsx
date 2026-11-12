import Link from "next/link";

import {
  ActionForm,
  DateTimeInput,
  Field,
  inputClass,
  SubmitButton,
} from "@/components/action-form";
import { formatDateTime, Section } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import type { CaseDetail, CriterionView, TeamView, WorkspaceMemberView } from "@/lib/types";
import { cn } from "@/lib/utils";

import {
  addCriterionAction,
  addTaskAction,
  bulkTasksAction,
  setCriterionStatusAction,
  setStepAction,
  setTaskStatusAction,
} from "../actions";
import { CRITERION_LABEL, PRIORITY_LABEL } from "../labels";

type Ctx = { workspaceId: string; caseId: string; detail: CaseDetail };

/** One select for member or team assignees ("user:<id>" / "team:<id>"). */
export function AssigneeSelect({
  id,
  members,
  teams,
  defaultValue = "",
}: {
  id: string;
  members: WorkspaceMemberView[];
  teams: TeamView[];
  defaultValue?: string;
}) {
  return (
    <select id={id} name="assignee" defaultValue={defaultValue} className={inputClass}>
      <option value="">Unassigned</option>
      <optgroup label="Members">
        {members
          .filter((m) => m.status === "active")
          .map((m) => (
            <option key={m.user_id} value={`user:${m.user_id}`}>
              {m.name}
            </option>
          ))}
      </optgroup>
      {teams.length ? (
        <optgroup label="Teams">
          {teams.map((t) => (
            <option key={t.id} value={`team:${t.id}`}>
              {t.name}
            </option>
          ))}
        </optgroup>
      ) : null}
    </select>
  );
}

export function TasksSection({
  workspaceId,
  caseId,
  detail: c,
  members,
  teams,
}: Ctx & { members: WorkspaceMemberView[]; teams: TeamView[] }) {
  const manage = c.allowed_actions.includes("add_task");
  const open = c.tasks.filter((t) => t.status === "open");
  const base = `/w/${workspaceId}/cases/${caseId}/tasks`;
  return (
    <Section
      title="Tasks"
      description={`${c.open_tasks} open${c.overdue_tasks ? ` · ${c.overdue_tasks} overdue` : ""}${
        open.some((t) => t.blocked_by.length) ? " · some wait on other tasks" : ""
      }`}
    >
      {c.tasks.length === 0 ? (
        <p className="text-muted-foreground rounded-lg border p-4 text-sm">No tasks yet.</p>
      ) : (
        <ul className="divide-y rounded-lg border">
          {c.tasks.map((t) => {
            const blocked = t.status === "open" && t.blocked_by.length > 0;
            return (
              <li key={t.id} className="flex items-center gap-3 px-4 py-2.5 text-sm">
                {manage && t.status === "open" ? (
                  <input
                    type="checkbox"
                    name="task"
                    value={t.id}
                    form="bulk-tasks"
                    aria-label={`Select ${t.title}`}
                  />
                ) : null}
                <ActionForm
                  action={setTaskStatusAction.bind(
                    null,
                    workspaceId,
                    caseId,
                    t.id,
                    t.status === "done" ? "open" : "done",
                  )}
                >
                  <button
                    type="submit"
                    disabled={blocked || t.status === "done"}
                    title={
                      blocked
                        ? `Waits for: ${t.blocked_by.join(", ")}`
                        : t.status === "done"
                          ? "Reopen from the task page (needs a reason)"
                          : "Complete"
                    }
                    aria-label={`Complete ${t.title}`}
                    className={cn(
                      "grid size-4 place-items-center rounded border text-[10px] disabled:cursor-not-allowed",
                      t.status === "done"
                        ? "bg-foreground text-background border-foreground"
                        : blocked
                          ? "border-dashed opacity-60"
                          : "hover:border-foreground",
                    )}
                  >
                    {t.status === "done" ? "✓" : ""}
                  </button>
                </ActionForm>
                <Link
                  href={`${base}/${t.id}`}
                  className={cn(
                    "min-w-0 flex-1 underline-offset-2 hover:underline",
                    t.status !== "open" && "text-muted-foreground line-through",
                  )}
                >
                  {t.title}
                </Link>
                {t.priority === "urgent" || t.priority === "high" ? (
                  <Badge tone={t.priority === "urgent" ? "danger" : "warning"}>
                    {PRIORITY_LABEL[t.priority]}
                  </Badge>
                ) : null}
                {blocked ? <Badge tone="muted">Waiting</Badge> : null}
                {t.needs_input_from_name ? (
                  <Badge tone="warning">Asked {t.needs_input_from_name}</Badge>
                ) : null}
                <span className="text-muted-foreground hidden text-xs sm:inline">
                  {t.assignee_name ?? t.assignee_team_name ?? "Unassigned"}
                </span>
                {t.due_at && t.status === "open" ? (
                  t.overdue ? (
                    <Badge tone="danger">Overdue</Badge>
                  ) : (
                    <span className="text-muted-foreground hidden text-xs sm:inline">
                      {formatDateTime(t.due_at)}
                    </span>
                  )
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
      {manage && open.length > 1 ? (
        <ActionForm
          id="bulk-tasks"
          action={bulkTasksAction.bind(null, workspaceId, caseId)}
          className="flex-row flex-wrap items-center gap-2 text-sm"
        >
          <span className="text-muted-foreground text-xs">Selected:</span>
          <select
            name="action"
            defaultValue="complete"
            aria-label="Bulk action"
            className={cn(inputClass, "h-8 w-auto")}
          >
            <option value="complete">Complete</option>
            <option value="reassign">Reassign to…</option>
          </select>
          <select
            name="bulk_assignee"
            defaultValue=""
            aria-label="New assignee"
            className={cn(inputClass, "h-8 w-auto")}
          >
            <option value="">(for reassign)</option>
            {members
              .filter((m) => m.status === "active")
              .map((m) => (
                <option key={m.user_id} value={m.user_id}>
                  {m.name}
                </option>
              ))}
          </select>
          <input
            name="reason"
            placeholder="Reason (needed to reassign)"
            aria-label="Reason"
            maxLength={4000}
            className={cn(inputClass, "h-8 w-56")}
          />
          <SubmitButton size="sm" variant="outline" pendingLabel="…">
            Apply
          </SubmitButton>
          <span className="text-muted-foreground text-xs">
            Tasks waiting on others are skipped, never forced.
          </span>
        </ActionForm>
      ) : null}
      {manage ? (
        <details>
          <summary className="text-muted-foreground hover:text-foreground cursor-pointer text-sm">
            Add a task
          </summary>
          <ActionForm action={addTaskAction.bind(null, workspaceId, caseId)} className="mt-2">
            <Field label="Title" htmlFor="task-title">
              <input
                id="task-title"
                name="title"
                required
                maxLength={200}
                placeholder="Walk through the runbook"
                className={inputClass}
              />
            </Field>
            <div className="grid gap-3 sm:grid-cols-3">
              <Field label="Assignee" htmlFor="task-assignee">
                <AssigneeSelect id="task-assignee" members={members} teams={teams} />
              </Field>
              <Field label="Priority" htmlFor="task-priority">
                <select
                  id="task-priority"
                  name="priority"
                  defaultValue="normal"
                  className={inputClass}
                >
                  {Object.entries(PRIORITY_LABEL).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Due" htmlFor="task-due">
                <DateTimeInput id="task-due" name="due_at" />
              </Field>
            </div>
            {open.length ? (
              <fieldset className="text-sm">
                <legend className="text-muted-foreground mb-1 text-xs">Waits for (optional)</legend>
                <div className="flex flex-wrap gap-x-4 gap-y-1">
                  {open.map((t) => (
                    <label key={t.id} className="flex items-center gap-1.5">
                      <input type="checkbox" name="depends_on" value={t.id} />
                      {t.title}
                    </label>
                  ))}
                </div>
              </fieldset>
            ) : null}
            {c.scope.length ? (
              <Field label="For responsibility (optional)" htmlFor="task-scope">
                <select id="task-scope" name="scope_item_id" defaultValue="" className={inputClass}>
                  <option value="">Whole case</option>
                  {c.scope.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.responsibility_name}
                    </option>
                  ))}
                </select>
              </Field>
            ) : null}
            <SubmitButton size="sm" pendingLabel="Adding…">
              Add task
            </SubmitButton>
          </ActionForm>
        </details>
      ) : null}
    </Section>
  );
}

const CRITERION_STATUS: Record<
  CriterionView["status"],
  { label: string; tone: "muted" | "neutral" | "danger" | "warning" }
> = {
  pending: { label: "Pending", tone: "muted" },
  met: { label: "Met", tone: "neutral" },
  blocked: { label: "Blocked", tone: "danger" },
  waived: { label: "Waived", tone: "warning" },
  needs_review: { label: "Needs review", tone: "warning" },
  unable_to_assess: { label: "Can't assess", tone: "warning" },
};

export function ReadinessSection({ workspaceId, caseId, detail: c }: Ctx) {
  const manage = c.allowed_actions.includes("add_criterion");
  return (
    <Section
      title="Readiness"
      description={`${c.readiness_met} of ${c.readiness_total} mandatory checks resolved${
        c.readiness_blocked ? ` · ${c.readiness_blocked} blocked or uncertain` : ""
      }`}
    >
      {c.readiness_reasons.length ? (
        <div className="rounded-lg border border-amber-600/30 bg-amber-50 p-3 text-sm text-amber-950 dark:bg-amber-950/30 dark:text-amber-100">
          <p className="font-medium">Why it isn&apos;t ready yet</p>
          <ul className="mt-1 list-disc pl-5">
            {c.readiness_reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {c.criteria.length === 0 ? (
        <p className="text-muted-foreground rounded-lg border p-4 text-sm">
          Readiness checks are created when the case is submitted.
        </p>
      ) : (
        <ul className="divide-y rounded-lg border">
          {c.criteria.map((r) => (
            <li key={r.id} className="flex flex-col gap-2 px-4 py-3 text-sm">
              <div className="flex flex-wrap items-center gap-3">
                <Badge tone={CRITERION_STATUS[r.status].tone}>
                  {CRITERION_STATUS[r.status].label}
                </Badge>
                <span className="min-w-0 flex-1">
                  {r.title}
                  <span className="text-muted-foreground block text-xs">
                    {CRITERION_LABEL[r.criterion_type] ?? r.criterion_type}
                    {r.mandatory ? "" : " · optional"}
                    {r.note ? ` · “${r.note}”` : ""}
                  </span>
                </span>
                {manage ? (
                  <ActionForm
                    action={setCriterionStatusAction.bind(null, workspaceId, caseId, r.id)}
                    className="flex-row items-center gap-2"
                  >
                    <select
                      name="status"
                      defaultValue={r.status === "pending" ? "met" : r.status}
                      aria-label={`Status for ${r.title}`}
                      className={`${inputClass} h-8 w-36`}
                    >
                      <option value="met">Met</option>
                      <option value="blocked">Blocked…</option>
                      <option value="needs_review">Needs review…</option>
                      <option value="unable_to_assess">Can&apos;t assess…</option>
                      <option value="pending">Pending</option>
                      <option value="waived">Waive…</option>
                    </select>
                    <input
                      name="note"
                      placeholder="Why (required unless met/pending)"
                      aria-label="Note"
                      maxLength={4000}
                      className={`${inputClass} h-8 w-52`}
                    />
                    <SubmitButton size="sm" variant="outline" pendingLabel="…">
                      Set
                    </SubmitButton>
                  </ActionForm>
                ) : null}
              </div>
              {r.checklist.length ? (
                <ol className="ml-1 flex flex-col gap-1 border-l pl-4">
                  {r.checklist.map((step, i) => (
                    <li key={i} className="flex items-center gap-2">
                      <ActionForm
                        action={setStepAction.bind(null, workspaceId, caseId, r.id, i, !step.done)}
                      >
                        <button
                          type="submit"
                          aria-label={step.done ? `Undo ${step.step}` : `Confirm ${step.step}`}
                          className={cn(
                            "grid size-4 place-items-center rounded border text-[10px]",
                            step.done
                              ? "bg-foreground text-background border-foreground"
                              : "hover:border-foreground",
                          )}
                        >
                          {step.done ? "✓" : ""}
                        </button>
                      </ActionForm>
                      <span className={step.done ? "text-muted-foreground" : undefined}>
                        {step.step}
                      </span>
                      {step.done && step.done_by ? (
                        <span className="text-muted-foreground text-xs">
                          {step.done_by}
                          {step.done_at ? ` · ${formatDateTime(step.done_at)}` : ""}
                        </span>
                      ) : null}
                    </li>
                  ))}
                </ol>
              ) : null}
            </li>
          ))}
        </ul>
      )}
      {manage ? (
        <details>
          <summary className="text-muted-foreground hover:text-foreground cursor-pointer text-sm">
            Add a readiness check or rehearsal
          </summary>
          <ActionForm action={addCriterionAction.bind(null, workspaceId, caseId)} className="mt-2">
            <div className="grid gap-3 sm:grid-cols-[1fr_12rem]">
              <Field label="Check" htmlFor="crit-title">
                <input
                  id="crit-title"
                  name="title"
                  required
                  maxLength={200}
                  placeholder="Recipient runs the month-end close"
                  className={inputClass}
                />
              </Field>
              <Field label="Type" htmlFor="crit-type">
                <select
                  id="crit-type"
                  name="criterion_type"
                  defaultValue="supervised_demo"
                  className={inputClass}
                >
                  {Object.entries(CRITERION_LABEL).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </select>
              </Field>
            </div>
            <Field label="Rehearsal steps (for rehearsals, one per line)" htmlFor="crit-steps">
              <textarea
                id="crit-steps"
                name="checklist"
                rows={3}
                placeholder={
                  "Confirm access to the billing console\nRun reconciliation with the owner watching"
                }
                className={cn(inputClass, "h-auto py-2")}
              />
            </Field>
            <p className="text-muted-foreground text-xs">
              A rehearsal is a supervised walk-through: people confirm each step. Relay never
              performs the steps or touches external systems.
            </p>
            <label className="flex items-center gap-2 text-xs">
              <input type="checkbox" name="mandatory" defaultChecked /> Mandatory
            </label>
            <SubmitButton size="sm" variant="outline">
              Add check
            </SubmitButton>
          </ActionForm>
        </details>
      ) : null}
    </Section>
  );
}
