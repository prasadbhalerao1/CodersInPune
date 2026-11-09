import Link from "next/link";

import {
  ActionForm,
  DateTimeInput,
  Field,
  inputClass,
  SubmitButton,
} from "@/components/action-form";
import { formatDateTime, Section } from "@/components/page";
import { Badge, CriticalityBadge, ROLE_LABEL } from "@/components/ui/badge";
import type {
  CaseDetail,
  WorkspaceMemberView,
  PersonView,
  ResponsibilitySummary,
  TeamView,
} from "@/lib/types";

import {
  addCriterionAction,
  addScopeAction,
  addTaskAction,
  decideAction,
  extendAction,
  removeScopeAction,
  setCriterionStatusAction,
  setTaskStatusAction,
  updateScopeAction,
} from "../actions";
import { CRITERION_LABEL } from "../labels";

type Ctx = { workspaceId: string; caseId: string; detail: CaseDetail };

const editable = (c: CaseDetail) => c.allowed_actions.includes("edit");

export function ScopeSection({
  workspaceId,
  caseId,
  detail: c,
  people,
  teams,
  responsibilities,
}: Ctx & { people: PersonView[]; teams: TeamView[]; responsibilities: ResponsibilitySummary[] }) {
  const inScope = new Set(c.scope.map((s) => s.responsibility_id));
  const candidates = responsibilities.filter((r) => !inScope.has(r.id));
  return (
    <Section
      title="Responsibilities in scope"
      description={
        c.case_type === "coverage"
          ? "Each cover holds the responsibility only for the coverage period."
          : "Each responsibility moves to its recipient on the effective date."
      }
    >
      {c.scope.length === 0 ? (
        <p className="rounded-lg border border-dashed p-4 text-sm">
          <span className="font-medium">Nothing in scope yet.</span>{" "}
          <span className="text-muted-foreground">Add the responsibilities this case moves.</span>
        </p>
      ) : (
        <ul className="divide-y rounded-lg border">
          {c.scope.map((item) => (
            <li key={item.id} className="flex flex-col gap-3 px-4 py-3">
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <Link
                  href={`/w/${workspaceId}/responsibilities/${item.responsibility_id}`}
                  className="font-medium hover:underline"
                >
                  {item.responsibility_name}
                </Link>
                <CriticalityBadge value={item.criticality} />
                <span className="text-muted-foreground text-xs">{ROLE_LABEL[item.role]}</span>
                <span className="text-muted-foreground ml-auto text-xs">
                  {item.current_owner_name ?? "Unowned"} →{" "}
                  <span className="text-foreground font-medium">
                    {item.exception_reason
                      ? "No transfer"
                      : (item.recipient?.name ?? "Choose recipient")}
                  </span>
                </span>
                {item.state === "applied" ? <Badge>Applied</Badge> : null}
                {item.state === "excepted" || item.exception_reason ? (
                  <Badge tone="warning">Exception</Badge>
                ) : null}
              </div>
              {editable(c) ? (
                <ActionForm
                  action={updateScopeAction.bind(null, workspaceId, caseId, item.id)}
                  className="bg-muted/30 rounded-md p-3"
                >
                  <div className="grid gap-3 sm:grid-cols-2">
                    <Field
                      label={c.case_type === "coverage" ? "Covered by" : "Recipient"}
                      htmlFor={`r-${item.id}`}
                    >
                      <select
                        id={`r-${item.id}`}
                        name="recipient"
                        defaultValue={
                          item.recipient ? `${item.recipient.type}:${item.recipient.id}` : ""
                        }
                        className={inputClass}
                      >
                        <option value="">No recipient</option>
                        <optgroup label="People">
                          {people.map((p) => (
                            <option key={p.id} value={`person:${p.id}`}>
                              {p.display_name}
                            </option>
                          ))}
                        </optgroup>
                        <optgroup label="Teams">
                          {teams.map((t) => (
                            <option key={t.id} value={`team:${t.id}`}>
                              {t.name}
                            </option>
                          ))}
                        </optgroup>
                      </select>
                    </Field>
                    <Field label="Exception (instead of a recipient)" htmlFor={`e-${item.id}`}>
                      <input
                        id={`e-${item.id}`}
                        name="exception_reason"
                        defaultValue={item.exception_reason ?? ""}
                        maxLength={4000}
                        placeholder="e.g. responsibility retired"
                        className={inputClass}
                      />
                    </Field>
                  </div>
                  <Field label="Handover notes and outstanding work" htmlFor={`n-${item.id}`}>
                    <textarea
                      id={`n-${item.id}`}
                      name="handover_notes"
                      defaultValue={item.handover_notes ?? ""}
                      rows={2}
                      maxLength={4000}
                      className={`${inputClass} h-auto py-2`}
                    />
                  </Field>
                  <div className="flex items-center gap-2">
                    <SubmitButton size="sm" variant="outline">
                      Save
                    </SubmitButton>
                  </div>
                </ActionForm>
              ) : item.handover_notes ? (
                <p className="text-muted-foreground text-sm whitespace-pre-line">
                  {item.handover_notes}
                </p>
              ) : null}
              {editable(c) ? (
                <ActionForm action={removeScopeAction.bind(null, workspaceId, caseId, item.id)}>
                  <SubmitButton
                    size="sm"
                    variant="ghost"
                    pendingLabel="Removing…"
                    confirm="Remove this responsibility from the case?"
                  >
                    Remove from scope
                  </SubmitButton>
                </ActionForm>
              ) : null}
            </li>
          ))}
        </ul>
      )}
      {editable(c) && candidates.length > 0 ? (
        <ActionForm
          action={addScopeAction.bind(null, workspaceId, caseId)}
          className="flex-row flex-wrap items-end gap-2"
        >
          <Field label="Add responsibility" htmlFor="add-scope">
            <select
              id="add-scope"
              name="responsibility_id"
              defaultValue=""
              className={`${inputClass} min-w-64`}
            >
              <option value="" disabled>
                Choose…
              </option>
              {candidates.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Role" htmlFor="add-role">
            <select id="add-role" name="role" defaultValue="primary" className={inputClass}>
              <option value="primary">Primary</option>
              <option value="co_owner">Co-owner</option>
              <option value="backup">Backup</option>
            </select>
          </Field>
          <SubmitButton size="sm" variant="outline">
            Add
          </SubmitButton>
        </ActionForm>
      ) : null}
    </Section>
  );
}

export function TasksSection({
  workspaceId,
  caseId,
  detail: c,
  members,
}: Ctx & { members: WorkspaceMemberView[] }) {
  return (
    <Section
      title="Preparation tasks"
      description={`${c.open_tasks} open${c.overdue_tasks ? ` · ${c.overdue_tasks} overdue` : ""}`}
    >
      {c.tasks.length === 0 ? (
        <p className="text-muted-foreground rounded-lg border p-4 text-sm">No tasks yet.</p>
      ) : (
        <ul className="divide-y rounded-lg border">
          {c.tasks.map((t) => (
            <li key={t.id} className="flex items-center gap-3 px-4 py-2.5 text-sm">
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
                  aria-label={t.status === "done" ? `Reopen ${t.title}` : `Complete ${t.title}`}
                  className={`grid size-4 place-items-center rounded border text-[10px] ${t.status === "done" ? "bg-foreground text-background border-foreground" : "hover:border-foreground"}`}
                >
                  {t.status === "done" ? "✓" : ""}
                </button>
              </ActionForm>
              <span
                className={`min-w-0 flex-1 ${t.status === "done" ? "text-muted-foreground line-through" : ""}`}
              >
                {t.title}
              </span>
              <span className="text-muted-foreground text-xs">
                {t.assignee_name ?? "Unassigned"}
              </span>
              {t.due_at ? (
                t.overdue ? (
                  <Badge tone="danger">Overdue</Badge>
                ) : (
                  <span className="text-muted-foreground text-xs">{formatDateTime(t.due_at)}</span>
                )
              ) : null}
            </li>
          ))}
        </ul>
      )}
      {c.allowed_actions.includes("add_task") ? (
        <ActionForm
          action={addTaskAction.bind(null, workspaceId, caseId)}
          className="flex-row flex-wrap items-end gap-2"
        >
          <Field label="New task" htmlFor="task-title">
            <input
              id="task-title"
              name="title"
              required
              maxLength={200}
              placeholder="Walk through the runbook"
              className={`${inputClass} min-w-64`}
            />
          </Field>
          <Field label="Assignee" htmlFor="task-assignee">
            <select
              id="task-assignee"
              name="assignee_user_id"
              defaultValue=""
              className={inputClass}
            >
              <option value="">Unassigned</option>
              {members.map((m) => (
                <option key={m.user_id} value={m.user_id}>
                  {m.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Due" htmlFor="task-due">
            <DateTimeInput id="task-due" name="due_at" />
          </Field>
          <SubmitButton size="sm" variant="outline">
            Add task
          </SubmitButton>
        </ActionForm>
      ) : null}
    </Section>
  );
}

const CRITERION_STATUS = {
  pending: { label: "Pending", tone: "muted" },
  met: { label: "Met", tone: "neutral" },
  blocked: { label: "Blocked", tone: "danger" },
  waived: { label: "Waived", tone: "warning" },
} as const;

export function ReadinessSection({ workspaceId, caseId, detail: c }: Ctx) {
  const manage = c.allowed_actions.includes("add_criterion");
  return (
    <Section
      title="Readiness"
      description={`${c.readiness_met} of ${c.readiness_total} mandatory checks resolved${c.readiness_blocked ? ` · ${c.readiness_blocked} blocked` : ""}`}
    >
      {c.criteria.length === 0 ? (
        <p className="text-muted-foreground rounded-lg border p-4 text-sm">
          Readiness checks are created when the case is submitted.
        </p>
      ) : (
        <ul className="divide-y rounded-lg border">
          {c.criteria.map((r) => (
            <li key={r.id} className="flex flex-wrap items-center gap-3 px-4 py-2.5 text-sm">
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
                    className={`${inputClass} h-8 w-28`}
                  >
                    <option value="met">Met</option>
                    <option value="blocked">Blocked</option>
                    <option value="pending">Pending</option>
                    <option value="waived">Waive…</option>
                  </select>
                  <input
                    name="note"
                    placeholder="Note (required to waive)"
                    aria-label="Note"
                    maxLength={4000}
                    className={`${inputClass} h-8 w-44`}
                  />
                  <SubmitButton size="sm" variant="outline" pendingLabel="…">
                    Set
                  </SubmitButton>
                </ActionForm>
              ) : null}
            </li>
          ))}
        </ul>
      )}
      {manage ? (
        <ActionForm
          action={addCriterionAction.bind(null, workspaceId, caseId)}
          className="flex-row flex-wrap items-end gap-2"
        >
          <Field label="Add check" htmlFor="crit-title">
            <input
              id="crit-title"
              name="title"
              required
              maxLength={200}
              placeholder="Recipient ran a supervised deploy"
              className={`${inputClass} min-w-64`}
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
          <label className="flex h-9 items-center gap-2 text-xs">
            <input type="checkbox" name="mandatory" defaultChecked /> Mandatory
          </label>
          <SubmitButton size="sm" variant="outline">
            Add check
          </SubmitButton>
        </ActionForm>
      ) : null}
    </Section>
  );
}

export function ApprovalPanel({ workspaceId, caseId, detail: c }: Ctx) {
  const decide = c.allowed_actions.includes("decide");
  return (
    <Section
      title="Approval"
      description={
        c.critical ? "Critical scope: approver must differ from the initiator." : undefined
      }
    >
      <div className="flex flex-col gap-3 rounded-lg border p-4 text-sm">
        <p>
          {c.approved ? (
            <Badge>Approved · v{c.plan_version}</Badge>
          ) : (
            <Badge tone="muted">Not approved for v{c.plan_version}</Badge>
          )}
        </p>
        {c.approvals.length ? (
          <ul className="flex flex-col gap-2">
            {c.approvals.map((a) => (
              <li key={a.id} className={a.current ? "" : "text-muted-foreground"}>
                <span className="font-medium capitalize">{a.decision}</span> by{" "}
                {a.approver_name ?? "a member"} for v{a.plan_version}
                {a.current ? "" : " (superseded)"}
                <span className="block text-xs">{formatDateTime(a.decided_at)}</span>
                {a.sod_exception_reason ? (
                  <span className="block text-xs">Exception: “{a.sod_exception_reason}”</span>
                ) : null}
                {a.comment ? <span className="block text-xs">“{a.comment}”</span> : null}
              </li>
            ))}
          </ul>
        ) : null}
        {decide ? (
          <ActionForm action={decideAction.bind(null, workspaceId, caseId)}>
            <input
              name="comment"
              placeholder="Comment (optional)"
              aria-label="Comment"
              maxLength={4000}
              className={inputClass}
            />
            {c.critical ? (
              <input
                name="sod_exception_reason"
                placeholder="Separation-of-duties exception, if you initiated this case"
                aria-label="Separation-of-duties exception"
                maxLength={4000}
                className={inputClass}
              />
            ) : null}
            <div className="flex gap-2">
              <button
                type="submit"
                name="decision"
                value="approved"
                className="bg-primary text-primary-foreground h-8 rounded-lg px-3 text-sm font-medium"
              >
                Approve v{c.plan_version}
              </button>
              <button
                type="submit"
                name="decision"
                value="rejected"
                className="hover:bg-muted h-8 rounded-lg border px-3 text-sm"
              >
                Reject
              </button>
            </div>
          </ActionForm>
        ) : null}
      </div>
      {c.allowed_actions.includes("extend") ? (
        <ActionForm
          action={extendAction.bind(null, workspaceId, caseId)}
          className="rounded-lg border p-4"
        >
          <Field label="Extend coverage until" htmlFor="extend">
            <DateTimeInput id="extend" name="ends_at" />
          </Field>
          <SubmitButton size="sm" variant="outline">
            Extend
          </SubmitButton>
        </ActionForm>
      ) : null}
    </Section>
  );
}
