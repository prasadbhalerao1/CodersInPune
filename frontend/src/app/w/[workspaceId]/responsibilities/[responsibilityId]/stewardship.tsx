import Link from "next/link";

import {
  ActionForm,
  DateTimeInput,
  Field,
  inputClass,
  SubmitButton,
} from "@/components/action-form";
import { formatDateTime, Section } from "@/components/page";
import { Badge, ROLE_LABEL } from "@/components/ui/badge";
import type {
  AssetSummary,
  AssignmentView,
  ResponsibilityDetail,
  ResponsibilitySummary,
  StewardshipView,
  WorkspaceMemberView,
} from "@/lib/types";

import {
  addDependencyAction,
  correctAssignmentAction,
  grantAccessAction,
  removeDependencyAction,
  reviewResponsibilityAction,
  revokeAccessAction,
} from "../../actions";

const RELATIONSHIP = {
  depends_on: ["depends on", "is depended on by"],
  feeds: ["feeds", "is fed by"],
  escalates_to: ["escalates to", "receives escalations from"],
  shares_access: ["shares access with", "shares access with"],
} as const;

/** Review state, escalation, procedures and prerequisites: the facts a successor needs. */
export function StewardshipFacts({
  workspaceId,
  detail: r,
  manage,
}: {
  workspaceId: string;
  detail: ResponsibilityDetail;
  manage: boolean;
}) {
  const reviewed = r.last_reviewed_at
    ? `Reviewed ${formatDateTime(r.last_reviewed_at)}${r.last_reviewed_by_name ? ` by ${r.last_reviewed_by_name}` : ""}`
    : "Never reviewed";
  return (
    <Section
      title="Stewardship"
      description={`${reviewed} · reviewed every ${r.effective_review_days} days`}
      aside={
        manage ? (
          <div className="flex gap-2">
            {r.needs_verification ? (
              <ActionForm action={reviewResponsibilityAction.bind(null, workspaceId, r.id, true)}>
                <SubmitButton size="sm" pendingLabel="…">
                  Verify
                </SubmitButton>
              </ActionForm>
            ) : null}
            <ActionForm action={reviewResponsibilityAction.bind(null, workspaceId, r.id, false)}>
              <SubmitButton size="sm" variant="outline" pendingLabel="…">
                Mark reviewed
              </SubmitButton>
            </ActionForm>
          </div>
        ) : undefined
      }
    >
      <div className="flex flex-wrap gap-2">
        {r.restricted ? <Badge tone="warning">Restricted</Badge> : null}
        {r.needs_verification ? <Badge tone="warning">Needs human verification</Badge> : null}
        {r.review_due ? <Badge tone="danger">Review overdue</Badge> : null}
        {r.type_name ? <Badge tone="muted">{r.type_name}</Badge> : null}
      </div>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 rounded-lg border p-4 text-sm">
        <dt className="text-muted-foreground">Escalation</dt>
        <dd>
          {r.escalation_path ?? <span className="text-muted-foreground">Not recorded</span>}
          {r.escalation_contact ? (
            <span className="text-muted-foreground block text-xs">{r.escalation_contact}</span>
          ) : null}
        </dd>
        <dt className="text-muted-foreground">Accountable contact</dt>
        <dd>{r.accountable_person_name ?? <span className="text-muted-foreground">—</span>}</dd>
        <dt className="text-muted-foreground">Procedures</dt>
        <dd>
          {r.procedures.length ? (
            <ul className="list-disc pl-4">
              {r.procedures.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          ) : (
            <span className="text-muted-foreground">None recorded</span>
          )}
        </dd>
        <dt className="text-muted-foreground">Access needed</dt>
        <dd>
          {r.access_prerequisites.length ? (
            <ul className="list-disc pl-4">
              {r.access_prerequisites.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          ) : (
            <span className="text-muted-foreground">None recorded</span>
          )}
        </dd>
      </dl>
    </Section>
  );
}

export function DependenciesSection({
  workspaceId,
  responsibilityId,
  stewardship,
  manage,
  responsibilities,
  assets,
}: {
  workspaceId: string;
  responsibilityId: string;
  stewardship: StewardshipView;
  manage: boolean;
  responsibilities: ResponsibilitySummary[];
  assets: AssetSummary[];
}) {
  return (
    <Section
      title="Dependencies"
      description="What this relies on and what relies on it, with where each link came from."
    >
      {stewardship.dependencies.length ? (
        <ul className="divide-y rounded-lg border text-sm">
          {stewardship.dependencies.map((d) => (
            <li key={d.id} className="flex flex-wrap items-center gap-2 px-4 py-2.5">
              <span className="text-muted-foreground">
                {RELATIONSHIP[d.relationship][d.direction === "outgoing" ? 0 : 1]}
              </span>
              <Link
                href={`/w/${workspaceId}/${d.target_type === "asset" ? "assets" : "responsibilities"}/${d.target_id}`}
                className="font-medium underline-offset-2 hover:underline"
              >
                {d.target_name}
              </Link>
              <Badge tone="muted">{d.provenance.replace("_", " ")}</Badge>
              {d.note ? <span className="text-muted-foreground text-xs">“{d.note}”</span> : null}
              {manage && d.direction === "outgoing" ? (
                <ActionForm
                  action={removeDependencyAction.bind(null, workspaceId, responsibilityId, d.id)}
                  className="ml-auto"
                >
                  <SubmitButton size="sm" variant="ghost" pendingLabel="…">
                    Remove
                  </SubmitButton>
                </ActionForm>
              ) : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-muted-foreground rounded-lg border p-4 text-sm">
          No dependencies recorded.
        </p>
      )}
      {manage ? (
        <ActionForm
          action={addDependencyAction.bind(null, workspaceId, responsibilityId)}
          className="flex-row flex-wrap items-end gap-2"
        >
          <Field label="Relationship" htmlFor="dep-rel">
            <select
              id="dep-rel"
              name="relationship"
              defaultValue="depends_on"
              className={inputClass}
            >
              <option value="depends_on">Depends on</option>
              <option value="feeds">Feeds</option>
              <option value="escalates_to">Escalates to</option>
              <option value="shares_access">Shares access with</option>
            </select>
          </Field>
          <Field label="Target" htmlFor="dep-target">
            <select id="dep-target" name="target" required defaultValue="" className={inputClass}>
              <option value="" disabled>
                Choose…
              </option>
              <optgroup label="Responsibilities">
                {responsibilities
                  .filter((x) => x.id !== responsibilityId)
                  .map((x) => (
                    <option key={x.id} value={`responsibility:${x.id}`}>
                      {x.name}
                    </option>
                  ))}
              </optgroup>
              <optgroup label="Assets">
                {assets.map((a) => (
                  <option key={a.id} value={`asset:${a.id}`}>
                    {a.name}
                  </option>
                ))}
              </optgroup>
            </select>
          </Field>
          <Field label="Note (optional)" htmlFor="dep-note">
            <input id="dep-note" name="note" maxLength={4000} className={inputClass} />
          </Field>
          <SubmitButton size="sm" variant="outline" pendingLabel="Adding…">
            Add
          </SubmitButton>
        </ActionForm>
      ) : null}
    </Section>
  );
}

export function AccessSection({
  workspaceId,
  responsibilityId,
  stewardship,
  members,
}: {
  workspaceId: string;
  responsibilityId: string;
  stewardship: StewardshipView;
  members: WorkspaceMemberView[];
}) {
  const granted = new Set(stewardship.access.map((a) => a.user_id));
  return (
    <Section
      title="Who can see this"
      description="Restricted: owners, admins and current holders, plus the members below."
    >
      {stewardship.access.length ? (
        <ul className="divide-y rounded-lg border text-sm">
          {stewardship.access.map((a) => (
            <li key={a.user_id} className="flex items-center gap-2 px-4 py-2">
              <span className="flex-1">{a.name}</span>
              <span className="text-muted-foreground text-xs">{formatDateTime(a.granted_at)}</span>
              <ActionForm
                action={revokeAccessAction.bind(null, workspaceId, responsibilityId, a.user_id)}
              >
                <SubmitButton size="sm" variant="ghost" pendingLabel="…">
                  Revoke
                </SubmitButton>
              </ActionForm>
            </li>
          ))}
        </ul>
      ) : null}
      <ActionForm
        action={grantAccessAction.bind(null, workspaceId, responsibilityId)}
        className="flex-row items-end gap-2"
      >
        <select name="user_id" defaultValue="" aria-label="Member" className={inputClass}>
          <option value="">Grant access to…</option>
          {members
            .filter((m) => m.status === "active" && !granted.has(m.user_id))
            .map((m) => (
              <option key={m.user_id} value={m.user_id}>
                {m.name}
              </option>
            ))}
        </select>
        <SubmitButton size="sm" variant="outline" pendingLabel="…">
          Grant
        </SubmitButton>
      </ActionForm>
    </Section>
  );
}

/** Fix when an assignment really started/ended. The original stays in history. */
export function CorrectAssignment({
  workspaceId,
  responsibilityId,
  assignment: a,
}: {
  workspaceId: string;
  responsibilityId: string;
  assignment: AssignmentView;
}) {
  return (
    <details className="text-xs">
      <summary className="text-muted-foreground hover:text-foreground cursor-pointer">
        Correct the record…
      </summary>
      <ActionForm
        action={correctAssignmentAction.bind(null, workspaceId, responsibilityId, a.id)}
        className="mt-2 rounded-lg border p-3"
      >
        <p className="text-muted-foreground">
          {a.assignee.name} as {ROLE_LABEL[a.role as keyof typeof ROLE_LABEL].toLowerCase()}. Use
          this when the dates recorded were wrong; the original stays in the history.
        </p>
        <div className="grid gap-2 sm:grid-cols-2">
          <Field label="Really started" htmlFor={`from-${a.id}`}>
            <DateTimeInput id={`from-${a.id}`} name="valid_from" defaultValue={a.valid_from} />
          </Field>
          <Field label="Ended (empty = still holds it)" htmlFor={`to-${a.id}`}>
            <DateTimeInput id={`to-${a.id}`} name="valid_to" defaultValue={a.valid_to} />
          </Field>
        </div>
        <input
          name="reason"
          required
          maxLength={4000}
          placeholder="Why the record is corrected"
          aria-label="Reason"
          className={inputClass}
        />
        <SubmitButton size="sm" variant="outline" pendingLabel="Saving…">
          Save correction
        </SubmitButton>
      </ActionForm>
    </details>
  );
}
