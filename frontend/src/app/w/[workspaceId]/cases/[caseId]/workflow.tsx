import Link from "next/link";

import {
  ActionForm,
  DateTimeInput,
  Field,
  inputClass,
  SubmitButton,
} from "@/components/action-form";
import { formatDateTime, Section } from "@/components/page";
import { Badge, CaseStatusBadge } from "@/components/ui/badge";
import type {
  CaseDetail,
  CaseStatus,
  ParticipantView,
  PersonView,
  WorkspaceMemberView,
} from "@/lib/types";
import { cn } from "@/lib/utils";

import {
  addBlockerAction,
  addParticipantAction,
  declineScopeAction,
  removeParticipantAction,
  reopenCaseAction,
  resolveBlockerAction,
  splitCaseAction,
  transitionAction,
  updateCaseDetailsAction,
} from "../actions";
import { CASE_TYPES, PRIORITY_LABEL, STATUS_LABEL } from "../labels";

type Ctx = { workspaceId: string; caseId: string; detail: CaseDetail };

export const CASE_TABS = [
  ["overview", "Overview"],
  ["impact", "Impact"],
  ["knowledge", "Knowledge"],
  ["tasks", "Tasks & readiness"],
  ["people", "People"],
  ["approvals", "Approvals"],
  ["activity", "Activity"],
] as const;
export type CaseTab = (typeof CASE_TABS)[number][0];

export function CaseTabs({
  workspaceId,
  caseId,
  current,
  counts,
}: {
  workspaceId: string;
  caseId: string;
  current: CaseTab | "analysis" | "interview" | "capsules";
  counts?: Partial<Record<CaseTab, number>>;
}) {
  const base = `/w/${workspaceId}/cases/${caseId}`;
  const link = (href: string, label: string, active: boolean, count?: number) => (
    <Link
      key={href}
      href={href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "-mb-px flex items-center gap-1.5 border-b-2 px-1 pb-2 text-sm whitespace-nowrap",
        active
          ? "border-foreground font-medium"
          : "text-muted-foreground hover:text-foreground border-transparent",
      )}
    >
      {label}
      {count ? <span className="text-muted-foreground text-xs tabular-nums">{count}</span> : null}
    </Link>
  );
  return (
    <nav aria-label="Case sections" className="flex gap-4 overflow-x-auto border-b px-6 pt-3">
      {CASE_TABS.map(([tab, label]) =>
        link(
          tab === "overview" ? base : `${base}?tab=${tab}`,
          label,
          current === tab,
          counts?.[tab],
        ),
      )}
      <span aria-hidden className="bg-border mx-1 mb-2 w-px" />
      {link(`${base}/analysis`, "Analysis", current === "analysis")}
      {link(`${base}/interview`, "Interview", current === "interview")}
      {link(`${base}/capsules`, "Capsules", current === "capsules")}
    </nav>
  );
}

// ---------------------------------------------------------------- progress & next step

const PHASES = [
  { label: "Scope", statuses: ["draft", "investigating", "awaiting_input", "reopened"] },
  { label: "Plan & approve", statuses: ["planning", "awaiting_review", "ready_for_transfer"] },
  { label: "Hand over", statuses: ["executing", "verification"] },
  { label: "Complete", statuses: ["completed"] },
] as const satisfies readonly { label: string; statuses: readonly CaseStatus[] }[];

export function CaseProgress({ detail: c }: { detail: CaseDetail }) {
  const effective = c.status === "blocked" ? (c.blocked_from ?? "draft") : c.status;
  const reached = PHASES.findIndex((p) => (p.statuses as readonly string[]).includes(effective));
  return (
    <ol className="flex flex-wrap items-center gap-x-6 gap-y-2 text-xs" aria-label="Progress">
      {PHASES.map((phase, i) => {
        const done = c.status === "completed" || (reached >= 0 && i < reached);
        const current = i === reached && c.status !== "completed";
        return (
          <li
            key={phase.label}
            className={cn("flex items-center gap-2", !done && !current && "text-muted-foreground")}
          >
            <span
              aria-hidden
              className={cn(
                "grid size-5 place-items-center rounded-full border text-[10px] font-medium",
                done && "bg-foreground text-background border-foreground",
                current &&
                  (c.status === "blocked" ? "border-red-600 text-red-700" : "border-foreground"),
              )}
            >
              {done ? "✓" : current && c.status === "blocked" ? "!" : i + 1}
            </span>
            <span className={current ? "font-medium" : undefined}>
              {phase.label}
              {current && phase.label !== "Complete" ? (
                <span className="text-muted-foreground font-normal">
                  {" "}
                  · {STATUS_LABEL[c.status]}
                </span>
              ) : null}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

export function nextStep(c: CaseDetail): string {
  const open = c.blockers.filter((b) => !b.resolved_at).length;
  switch (c.status) {
    case "draft":
    case "investigating":
    case "reopened":
      return "Choose a recipient (or record an exception) for every responsibility, then submit the plan.";
    case "awaiting_input":
      return "Waiting for input from the people involved before the plan can be completed.";
    case "planning":
      return c.approved
        ? "Approved. Execute to apply the ownership changes."
        : "Waiting for approval of the current plan.";
    case "awaiting_review":
      return "The plan is with reviewers. Approving it makes the case ready for transfer.";
    case "ready_for_transfer":
      return "Approved and ready. Execute to apply the ownership changes.";
    case "executing":
    case "verification":
      return c.readiness_met < c.readiness_total
        ? `Readiness ${c.readiness_met}/${c.readiness_total}. Resolve the remaining checks, then complete.`
        : "Readiness is complete. Verify and complete the case.";
    case "blocked":
      return `Blocked by ${open} open blocker${open === 1 ? "" : "s"}. Resolving them returns the case to ${STATUS_LABEL[c.blocked_from ?? "draft"].toLowerCase()}.`;
    case "completed":
      return c.outcome === "completed_with_exceptions"
        ? "Completed with recorded exceptions."
        : "Completed.";
    case "cancelled":
      return "Cancelled. Ownership changes already applied stay as they are.";
  }
}

// ---------------------------------------------------------------- status controls

export function StatusControls({ workspaceId, caseId, detail: c }: Ctx) {
  const can = (a: CaseDetail["allowed_actions"][number]) => c.allowed_actions.includes(a);
  if (!c.transitions.length && !can("reopen")) return null;
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      {c.transitions.length ? <span className="text-muted-foreground text-xs">Move to</span> : null}
      {c.transitions.map((to) => (
        <ActionForm key={to} action={transitionAction.bind(null, workspaceId, caseId, to)}>
          <SubmitButton size="sm" variant="outline" pendingLabel="Moving…">
            {STATUS_LABEL[to]}
          </SubmitButton>
        </ActionForm>
      ))}
      {can("reopen") ? (
        <details className="group">
          <summary className="text-muted-foreground hover:text-foreground cursor-pointer text-xs">
            Reopen case…
          </summary>
          <ActionForm action={reopenCaseAction.bind(null, workspaceId, caseId)} className="mt-2">
            <input
              name="reason"
              required
              maxLength={4000}
              placeholder="Why it needs more work"
              aria-label="Reason for reopening"
              className={inputClass}
            />
            <SubmitButton size="sm" pendingLabel="Reopening…">
              Reopen
            </SubmitButton>
            <p className="text-muted-foreground text-xs">
              The closure stays on record. Ownership already handed over is not undone.
            </p>
          </ActionForm>
        </details>
      ) : null}
    </div>
  );
}

// ---------------------------------------------------------------- blockers

export function BlockersPanel({
  workspaceId,
  caseId,
  detail: c,
  members,
}: Ctx & { members: WorkspaceMemberView[] }) {
  const open = c.blockers.filter((b) => !b.resolved_at);
  const resolved = c.blockers.filter((b) => b.resolved_at);
  const canAdd = c.allowed_actions.includes("add_blocker");
  if (!open.length && !resolved.length && !canAdd) return null;
  return (
    <Section
      title="Blockers"
      description="An open blocker pauses the case; it resumes where it was once all are resolved."
    >
      {open.length ? (
        <ul className="divide-y rounded-lg border border-red-600/25">
          {open.map((b) => (
            <li key={b.id} className="flex flex-col gap-2 px-4 py-3 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="danger">Blocking</Badge>
                {b.escalation_due ? <Badge tone="warning">Escalated</Badge> : null}
                <span className="font-medium">{b.description}</span>
              </div>
              <p className="text-muted-foreground text-xs">
                {b.owner_name ? `Owner: ${b.owner_name} · ` : "No owner · "}
                Raised by {b.created_by_name ?? "—"} {formatDateTime(b.created_at)} ·{" "}
                {b.escalation_due ? "escalated" : "escalates"} {formatDateTime(b.escalate_at)}
              </p>
              {c.allowed_actions.includes("update") ? (
                <ActionForm
                  action={resolveBlockerAction.bind(null, workspaceId, caseId, b.id)}
                  className="flex-row flex-wrap items-center"
                >
                  <input
                    name="resolution"
                    required
                    maxLength={4000}
                    placeholder="How it was resolved"
                    aria-label="Resolution"
                    className={cn(inputClass, "h-8 min-w-0 flex-1")}
                  />
                  <SubmitButton size="sm" variant="outline" pendingLabel="…">
                    Resolve
                  </SubmitButton>
                </ActionForm>
              ) : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-muted-foreground text-sm">No open blockers.</p>
      )}
      {canAdd ? (
        <details>
          <summary className="text-muted-foreground hover:text-foreground cursor-pointer text-sm">
            Raise a blocker
          </summary>
          <ActionForm action={addBlockerAction.bind(null, workspaceId, caseId)} className="mt-2">
            <Field label="What is blocking the case" htmlFor="blocker-description">
              <input
                id="blocker-description"
                name="description"
                required
                maxLength={1000}
                className={inputClass}
              />
            </Field>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Owner (optional)" htmlFor="blocker-owner">
                <select
                  id="blocker-owner"
                  name="owner_user_id"
                  defaultValue=""
                  className={inputClass}
                >
                  <option value="">No owner</option>
                  {members
                    .filter((m) => m.status === "active")
                    .map((m) => (
                      <option key={m.user_id} value={m.user_id}>
                        {m.name}
                      </option>
                    ))}
                </select>
              </Field>
              <Field label="Escalate at (default by priority)" htmlFor="blocker-escalate">
                <DateTimeInput id="blocker-escalate" name="escalate_at" />
              </Field>
            </div>
            <SubmitButton size="sm" pendingLabel="Raising…">
              Raise blocker
            </SubmitButton>
          </ActionForm>
        </details>
      ) : null}
      {resolved.length ? (
        <details>
          <summary className="text-muted-foreground cursor-pointer text-xs">
            {resolved.length} resolved
          </summary>
          <ul className="mt-2 flex flex-col gap-1 text-xs">
            {resolved.map((b) => (
              <li key={b.id}>
                <span className="line-through">{b.description}</span> — {b.resolution} (
                {b.resolved_by_name ?? "—"}, {formatDateTime(b.resolved_at!)})
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </Section>
  );
}

// ---------------------------------------------------------------- incoming owner

export function DeclinePanel({ workspaceId, caseId, detail: c }: Ctx) {
  const mine = c.scope.filter((s) => s.can_decline);
  if (!mine.length) return null;
  return (
    <div className="rounded-lg border p-4 text-sm">
      <p className="font-medium">You are named as the incoming owner</p>
      <ul className="mt-2 flex flex-col gap-3">
        {mine.map((s) => (
          <li key={s.id} className="flex flex-col gap-1">
            <span>
              {s.responsibility_name}
              {s.current_owner_name ? (
                <span className="text-muted-foreground"> · from {s.current_owner_name}</span>
              ) : null}
            </span>
            <details>
              <summary className="text-muted-foreground hover:text-foreground cursor-pointer text-xs">
                I can&apos;t take this on
              </summary>
              <ActionForm
                action={declineScopeAction.bind(null, workspaceId, caseId, s.id)}
                className="mt-2"
              >
                <input
                  name="reason"
                  required
                  maxLength={4000}
                  placeholder="Why (the coordinator sees this)"
                  aria-label="Reason for declining"
                  className={inputClass}
                />
                <SubmitButton size="sm" variant="outline" pendingLabel="…">
                  Decline assignment
                </SubmitButton>
              </ActionForm>
            </details>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ---------------------------------------------------------------- facts & details

export function CaseFacts({ detail: c, workspaceId }: { detail: CaseDetail; workspaceId: string }) {
  const caseLink = (id: string, title: string) => (
    <Link href={`/w/${workspaceId}/cases/${id}`} className="underline-offset-2 hover:underline">
      {title}
    </Link>
  );
  const row = (label: string, value: React.ReactNode) => (
    <>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="min-w-0">{value}</dd>
    </>
  );
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 rounded-lg border p-4 text-sm">
      {row("Case type", CASE_TYPES[c.case_type].label)}
      {row(
        "Priority",
        c.priority === "urgent" || c.priority === "high" ? (
          <Badge tone={c.priority === "urgent" ? "danger" : "warning"}>
            {PRIORITY_LABEL[c.priority]}
          </Badge>
        ) : (
          PRIORITY_LABEL[c.priority]
        ),
      )}
      {c.affected_person_name
        ? row(c.case_type === "onboarding" ? "Joining" : "Person", c.affected_person_name)
        : null}
      {c.project_asset_id && c.project_asset_name
        ? row(
            "Project",
            <Link
              href={`/w/${workspaceId}/assets/${c.project_asset_id}`}
              className="underline-offset-2 hover:underline"
            >
              {c.project_asset_name}
            </Link>,
          )
        : null}
      {row(c.case_type === "coverage" ? "From" : "Ownership changes", formatDateTime(c.starts_at))}
      {c.ends_at ? row("Until", formatDateTime(c.ends_at)) : null}
      {row(
        "Due",
        c.due_at ? (
          <span className={c.overdue ? "font-medium text-red-700 dark:text-red-300" : undefined}>
            {formatDateTime(c.due_at)}
            {c.overdue ? " · overdue" : ""}
          </span>
        ) : (
          "—"
        ),
      )}
      {row("Time zone", c.time_zone)}
      {row("Coordinator", c.coordinator_name ?? "—")}
      {row("Accountable", c.accountable_manager_name ?? "—")}
      {row("Plan version", <span className="tabular-nums">v{c.plan_version}</span>)}
      {c.reopen_count ? row("Reopened", `${c.reopen_count}×`) : null}
      {c.parent ? row("Split from", caseLink(c.parent.id, c.parent.title)) : null}
      {c.children.length
        ? row(
            "Split into",
            <ul>
              {c.children.map((child) => (
                <li key={child.id} className="flex items-center gap-2">
                  {caseLink(child.id, child.title)}
                </li>
              ))}
            </ul>,
          )
        : null}
    </dl>
  );
}

export function DuplicateNotice({
  detail: c,
  workspaceId,
}: {
  detail: CaseDetail;
  workspaceId: string;
}) {
  if (!c.duplicates.length) return null;
  return (
    <div className="rounded-lg border border-amber-600/30 bg-amber-50 p-3 text-sm text-amber-950 dark:bg-amber-950/30 dark:text-amber-100">
      <p className="font-medium">Another open case covers the same person or project</p>
      <ul className="mt-1">
        {c.duplicates.map((d) => (
          <li key={d.id}>
            <Link href={`/w/${workspaceId}/cases/${d.id}`} className="underline underline-offset-2">
              {d.title}
            </Link>{" "}
            · {STATUS_LABEL[d.status]}
          </li>
        ))}
      </ul>
      {c.duplicate_override_reason ? (
        <p className="mt-1 text-xs">Kept separate because: {c.duplicate_override_reason}</p>
      ) : null}
    </div>
  );
}

const ZONES = [
  "UTC",
  "Asia/Kolkata",
  "Europe/London",
  "Europe/Berlin",
  "America/New_York",
  "America/Los_Angeles",
  "Asia/Singapore",
  "Australia/Sydney",
];

export function CaseDetailsForm({
  workspaceId,
  caseId,
  detail: c,
  members,
}: Ctx & { members: WorkspaceMemberView[] }) {
  if (!c.allowed_actions.includes("update")) return null;
  const active = members.filter((m) => m.status === "active");
  const zones = ZONES.includes(c.time_zone) ? ZONES : [c.time_zone, ...ZONES];
  return (
    <details className="rounded-lg border p-4">
      <summary className="cursor-pointer text-sm font-medium">
        Edit priority, dates and people
      </summary>
      <ActionForm action={updateCaseDetailsAction.bind(null, workspaceId, caseId)} className="mt-3">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Priority" htmlFor="priority">
            <select id="priority" name="priority" defaultValue={c.priority} className={inputClass}>
              {Object.entries(PRIORITY_LABEL).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Time zone" htmlFor="time_zone">
            <select
              id="time_zone"
              name="time_zone"
              defaultValue={c.time_zone}
              className={inputClass}
            >
              {zones.map((z) => (
                <option key={z}>{z}</option>
              ))}
            </select>
          </Field>
          <Field label="Case due" htmlFor="due_at">
            <DateTimeInput id="due_at" name="due_at" defaultValue={c.due_at} />
          </Field>
          <Field label="Approval needed by" htmlFor="approval_due_at">
            <DateTimeInput
              id="approval_due_at"
              name="approval_due_at"
              defaultValue={c.approval_due_at}
            />
          </Field>
          <Field label="Accountable manager" htmlFor="accountable">
            <select
              id="accountable"
              name="accountable_manager_user_id"
              defaultValue={c.accountable_manager_user_id ?? ""}
              className={inputClass}
            >
              <option value="">Not set</option>
              {active.map((m) => (
                <option key={m.user_id} value={m.user_id}>
                  {m.name}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Delegated approver" htmlFor="delegate">
            <select
              id="delegate"
              name="delegate_approver_user_id"
              defaultValue={c.delegate_approver_user_id ?? ""}
              className={inputClass}
            >
              <option value="">None</option>
              {active.map((m) => (
                <option key={m.user_id} value={m.user_id}>
                  {m.name}
                </option>
              ))}
            </select>
          </Field>
        </div>
        <p className="text-muted-foreground text-xs">
          Reminders follow the new deadlines; ones for old deadlines are dropped.
        </p>
        <SubmitButton size="sm" pendingLabel="Saving…">
          Save
        </SubmitButton>
      </ActionForm>
    </details>
  );
}

// ---------------------------------------------------------------- departure split

export function SplitPanel({ workspaceId, caseId, detail: c }: Ctx) {
  const planned = c.scope.filter((s) => s.state === "planned");
  if (!c.allowed_actions.includes("split") || planned.length < 2) return null;
  return (
    <details className="rounded-lg border p-4 text-sm">
      <summary className="cursor-pointer font-medium">Split into separate handovers</summary>
      <p className="text-muted-foreground mt-1 text-xs">
        Each chosen responsibility becomes its own transfer case (with its tasks and checks), so it
        can be approved and executed on its own timeline.
      </p>
      <ActionForm action={splitCaseAction.bind(null, workspaceId, caseId)} className="mt-2">
        <ul className="flex flex-col gap-1">
          {planned.map((s) => (
            <li key={s.id}>
              <label className="flex items-center gap-2">
                <input type="checkbox" name="item" value={s.id} />
                {s.responsibility_name}
              </label>
            </li>
          ))}
        </ul>
        <SubmitButton size="sm" variant="outline" pendingLabel="Splitting…">
          Create child cases
        </SubmitButton>
      </ActionForm>
    </details>
  );
}

// ---------------------------------------------------------------- people

const ROLE: Record<string, string> = {
  initiator: "Initiator",
  coordinator: "Coordinator",
  accountable_manager: "Accountable",
  approver: "Approver",
  verifier: "Verifier",
  reviewer: "Reviewer",
  contributor: "Contributor",
  observer: "Observer",
  incoming: "Incoming",
  outgoing: "Outgoing",
  assignee: "Assignee",
};

export function PeoplePanel({
  workspaceId,
  caseId,
  detail: c,
  participants,
  members,
  people,
}: Ctx & {
  participants: ParticipantView[];
  members: WorkspaceMemberView[];
  people: PersonView[];
}) {
  const manage = c.allowed_actions.includes("update") || c.allowed_actions.includes("reopen");
  return (
    <Section
      title="People"
      description="Everyone involved and why: derived from the case, plus people added explicitly."
    >
      <ul className="divide-y rounded-lg border">
        {participants.map((p) => (
          <li key={p.key} className="flex flex-wrap items-start gap-3 px-4 py-3 text-sm">
            <div className="min-w-0 flex-1">
              <p className="flex flex-wrap items-center gap-2 font-medium">
                {p.name}
                {p.roles.map((r) => (
                  <Badge key={r} tone="muted">
                    {ROLE[r] ?? r}
                  </Badge>
                ))}
                {p.kind === "person" ? (
                  <span className="text-muted-foreground text-xs font-normal">directory</span>
                ) : null}
              </p>
              <p className="text-muted-foreground text-xs">{p.why.join(" · ")}</p>
            </div>
            {manage
              ? p.participant_ids.map((id) => (
                  <ActionForm
                    key={id}
                    action={removeParticipantAction.bind(null, workspaceId, caseId, id)}
                  >
                    <SubmitButton size="sm" variant="ghost" pendingLabel="…">
                      Remove
                    </SubmitButton>
                  </ActionForm>
                ))
              : null}
          </li>
        ))}
      </ul>
      {manage ? (
        <details>
          <summary className="text-muted-foreground hover:text-foreground cursor-pointer text-sm">
            Add someone
          </summary>
          <ActionForm
            action={addParticipantAction.bind(null, workspaceId, caseId)}
            className="mt-2"
          >
            <div className="grid gap-3 sm:grid-cols-[1fr_10rem]">
              <Field label="Who" htmlFor="participant">
                <select
                  id="participant"
                  name="subject"
                  required
                  defaultValue=""
                  className={inputClass}
                >
                  <option value="" disabled>
                    Choose…
                  </option>
                  <optgroup label="Members">
                    {members
                      .filter((m) => m.status === "active")
                      .map((m) => (
                        <option key={m.user_id} value={`user:${m.user_id}`}>
                          {m.name}
                        </option>
                      ))}
                  </optgroup>
                  <optgroup label="Directory">
                    {people.map((p) => (
                      <option key={p.id} value={`person:${p.id}`}>
                        {p.display_name}
                      </option>
                    ))}
                  </optgroup>
                </select>
              </Field>
              <Field label="Role" htmlFor="participant-role">
                <select
                  id="participant-role"
                  name="role"
                  defaultValue="contributor"
                  className={inputClass}
                >
                  {["contributor", "reviewer", "verifier", "approver", "observer"].map((r) => (
                    <option key={r} value={r}>
                      {ROLE[r]}
                    </option>
                  ))}
                </select>
              </Field>
            </div>
            <Field label="Why they are involved" htmlFor="participant-why">
              <input
                id="participant-why"
                name="why"
                required
                maxLength={200}
                className={inputClass}
              />
            </Field>
            <SubmitButton size="sm" pendingLabel="Adding…">
              Add
            </SubmitButton>
          </ActionForm>
        </details>
      ) : null}
    </Section>
  );
}

// ---------------------------------------------------------------- status history

export function StatusHistory({ detail: c }: { detail: CaseDetail }) {
  return (
    <Section title="Status history" description="Every status change, who made it and why.">
      <ol className="flex flex-col gap-3 border-l pl-4 text-sm">
        {c.status_history.map((h, i) => (
          <li key={i} className="relative">
            <span
              aria-hidden
              className="bg-foreground absolute top-1.5 -left-[1.3rem] size-2 rounded-full"
            />
            <p className="flex flex-wrap items-center gap-2">
              {h.from_status ? (
                <>
                  <CaseStatusBadge value={h.from_status} />
                  <span aria-hidden>→</span>
                </>
              ) : null}
              <CaseStatusBadge value={h.to_status} />
              <span className="text-muted-foreground text-xs">
                {h.actor_name ?? "System"} · {formatDateTime(h.changed_at)}
              </span>
            </p>
            {h.reason ? <p className="text-muted-foreground mt-0.5 text-xs">{h.reason}</p> : null}
            {h.outcome ? (
              <p className="text-muted-foreground mt-0.5 text-xs">
                Previous closure: {h.outcome.replaceAll("_", " ")}
                {h.closed_at ? ` on ${formatDateTime(h.closed_at)}` : ""}
              </p>
            ) : null}
          </li>
        ))}
      </ol>
    </Section>
  );
}
