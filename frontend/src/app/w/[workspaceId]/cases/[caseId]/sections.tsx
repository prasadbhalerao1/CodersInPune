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
import type { CaseDetail, PersonView, ResponsibilitySummary, TeamView } from "@/lib/types";

import {
  addScopeAction,
  decideAction,
  extendAction,
  removeScopeAction,
  updateScopeAction,
} from "../actions";

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
