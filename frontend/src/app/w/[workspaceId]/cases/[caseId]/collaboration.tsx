import { ActionForm, inputClass, SubmitButton } from "@/components/action-form";
import { formatDateTime, Section } from "@/components/page";
import { Badge, CriticalityBadge, ROLE_LABEL } from "@/components/ui/badge";
import type { ActivityView, BriefingView, CaseDetail } from "@/lib/types";

import { setEmergencyAction } from "../actions";

const ACTION_LABEL: Record<string, string> = {
  "case.created": "Case created",
  "case.updated": "Case details updated",
  "case.scope_added": "Responsibility added",
  "case.scope_updated": "Scope updated",
  "case.scope_removed": "Responsibility removed",
  "case.submitted": "Submitted for approval",
  "case.approved": "Plan approved",
  "case.rejected": "Plan rejected",
  "case.executed": "Ownership changes applied",
  "case.extended": "Coverage extended",
  "case.completed": "Case completed",
  "case.cancelled": "Case cancelled",
  "case.task_added": "Task added",
  "case.task_updated": "Task updated",
  "case.criterion_added": "Readiness check added",
  "case.criterion_updated": "Readiness check updated",
  "case.emergency_raised": "Marked as emergency",
  "case.emergency_cleared": "Emergency cleared",
};

/** Highlights "@Name" for the members actually mentioned; the rest is plain text. */
function CommentBody({ comment }: { comment: ActivityView }) {
  const names = comment.mentions.map((m) => m.name).sort((a, b) => b.length - a.length);
  if (!names.length) return <>{comment.body}</>;
  const escape = (v: string) => v.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const parts = (comment.body ?? "").split(new RegExp(`(@(?:${names.map(escape).join("|")}))`));
  return (
    <>
      {parts.map((part, i) =>
        part.startsWith("@") && names.includes(part.slice(1)) ? (
          <span key={i} className="bg-foreground/[0.06] rounded px-0.5 font-medium">
            {part}
          </span>
        ) : (
          part
        ),
      )}
    </>
  );
}

export function ActivityPanel({
  activity,
  composer,
}: {
  activity: ActivityView[];
  composer?: React.ReactNode;
}) {
  return (
    <Section title="Activity" description="Comments from people, and everything Relay recorded.">
      {composer}
      {activity.length === 0 ? (
        <p className="text-muted-foreground text-sm">Nothing yet.</p>
      ) : (
        <ol className="flex flex-col gap-3">
          {activity.map((a) =>
            a.kind === "comment" ? (
              <li key={a.id} className="rounded-lg border px-4 py-3 text-sm">
                <p className="text-muted-foreground mb-1 text-xs">
                  <span className="text-foreground font-medium">{a.actor_name ?? "Member"}</span> ·{" "}
                  {formatDateTime(a.occurred_at)}
                </p>
                <p className="whitespace-pre-line">
                  <CommentBody comment={a} />
                </p>
              </li>
            ) : (
              <li key={a.id} className="text-muted-foreground flex gap-3 px-1 text-xs">
                <span aria-hidden className="bg-border mt-1.5 size-1.5 shrink-0 rounded-full" />
                <span>
                  <span className="text-foreground/80">
                    {ACTION_LABEL[a.action ?? ""] ?? a.action}
                  </span>{" "}
                  · {a.actor_name ?? "Relay"} · {formatDateTime(a.occurred_at)}
                </span>
              </li>
            ),
          )}
        </ol>
      )}
    </Section>
  );
}

export function EmergencyBanner({ detail }: { detail: CaseDetail }) {
  if (!detail.emergency) return null;
  return (
    <div
      role="alert"
      className="flex items-start gap-3 border-b border-red-600/20 bg-red-50 px-6 py-3 text-sm text-red-900 dark:bg-red-950/30 dark:text-red-200"
    >
      <span aria-hidden className="mt-1.5 size-2 shrink-0 rounded-full bg-red-600" />
      <p>
        <span className="font-semibold">Emergency.</span> {detail.emergency_reason} Approvals,
        readiness checks and ownership rules still apply.
      </p>
    </div>
  );
}

export function EmergencyControl({
  workspaceId,
  caseId,
  detail,
}: {
  workspaceId: string;
  caseId: string;
  detail: CaseDetail;
}) {
  if (!detail.allowed_actions.includes("set_emergency")) return null;
  if (detail.emergency) {
    return (
      <ActionForm action={setEmergencyAction.bind(null, workspaceId, caseId, false)}>
        <SubmitButton size="sm" variant="ghost" pendingLabel="…">
          Clear emergency
        </SubmitButton>
      </ActionForm>
    );
  }
  return (
    <details className="group rounded-lg border px-4 py-3 text-sm">
      <summary className="text-muted-foreground cursor-pointer list-none select-none">
        Mark as emergency…
      </summary>
      <ActionForm
        action={setEmergencyAction.bind(null, workspaceId, caseId, true)}
        className="mt-3"
      >
        <input
          name="reason"
          required
          maxLength={4000}
          placeholder="What makes this urgent?"
          aria-label="Reason"
          className={inputClass}
        />
        <p className="text-muted-foreground text-xs">
          Puts the case at the top of everyone&apos;s lists and notifies approvers. Nothing is
          skipped.
        </p>
        <div>
          <SubmitButton size="sm" variant="destructive">
            Mark as emergency
          </SubmitButton>
        </div>
      </ActionForm>
    </details>
  );
}

const RESTORATION: Record<
  BriefingView["items"][number]["restoration"],
  { label: string; tone: "neutral" | "muted" | "warning" }
> = {
  not_started: { label: "Cover not started", tone: "muted" },
  covering: { label: "Being covered", tone: "neutral" },
  restored: { label: "Back to normal", tone: "neutral" },
  excepted: { label: "Not covered", tone: "warning" },
};

export function BriefingSection({ briefing }: { briefing: BriefingView }) {
  const done = briefing.tasks.filter((t) => t.status === "done").length;
  return (
    <Section
      title="Return briefing"
      description={`${briefing.person_name ?? "The person"} was away ${formatDateTime(briefing.period_start)} → ${formatDateTime(briefing.period_end)}. Built from what Relay recorded.`}
    >
      <div className="flex flex-col divide-y rounded-lg border text-sm">
        <div className="px-4 py-3">
          <p className="text-muted-foreground mb-2 text-xs font-medium">What was covered</p>
          <ul className="flex flex-col gap-2">
            {briefing.items.map((i) => (
              <li key={i.responsibility_id} className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{i.responsibility_name}</span>
                <CriticalityBadge value={i.criticality} />
                <span className="text-muted-foreground">
                  {i.covered_by ? `covered by ${i.covered_by}` : (i.exception_reason ?? "no cover")}
                </span>
                <span className="ml-auto flex items-center gap-2">
                  <Badge tone={RESTORATION[i.restoration].tone}>
                    {RESTORATION[i.restoration].label}
                  </Badge>
                  {!i.original_owner_active ? <Badge tone="warning">Owner role ended</Badge> : null}
                </span>
                {i.handover_notes ? (
                  <p className="text-muted-foreground w-full text-xs">Notes: {i.handover_notes}</p>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
        <div className="px-4 py-3">
          <p className="text-muted-foreground mb-2 text-xs font-medium">
            Changes while away (
            {briefing.ownership_changes.length + briefing.responsibility_events.length})
          </p>
          {briefing.ownership_changes.length + briefing.responsibility_events.length === 0 ? (
            <p className="text-muted-foreground text-xs">Nothing changed.</p>
          ) : (
            <ul className="flex flex-col gap-1 text-xs">
              {briefing.ownership_changes.map((c, i) => (
                <li key={`c${i}`}>
                  {formatDateTime(c.changed_at)} · {c.responsibility_name}: {c.assignee_name}{" "}
                  {c.change_type === "assigned" ? "became" : "stopped being"}{" "}
                  {ROLE_LABEL[c.role].toLowerCase()}
                </li>
              ))}
              {briefing.responsibility_events.map((e, i) => (
                <li key={`e${i}`}>
                  {formatDateTime(e.occurred_at)} · {e.responsibility_name}:{" "}
                  {e.action.replace("responsibility.", "").replaceAll("_", " ")} by{" "}
                  {e.actor_name ?? "Relay"}
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="grid gap-4 px-4 py-3 sm:grid-cols-2">
          <div>
            <p className="text-muted-foreground mb-2 text-xs font-medium">
              Still open ({briefing.tasks.length - done})
            </p>
            {briefing.tasks.length === done ? (
              <p className="text-muted-foreground text-xs">Nothing outstanding.</p>
            ) : (
              <ul className="flex flex-col gap-1 text-xs">
                {briefing.tasks
                  .filter((t) => t.status !== "done")
                  .map((t, i) => (
                    <li key={i} className="font-medium">
                      ○ {t.title}
                      {t.assignee_name ? ` · ${t.assignee_name}` : ""}
                    </li>
                  ))}
              </ul>
            )}
          </div>
          <div>
            <p className="text-muted-foreground mb-2 text-xs font-medium">Done ({done})</p>
            {done === 0 ? (
              <p className="text-muted-foreground text-xs">No tasks completed.</p>
            ) : (
              <ul className="flex flex-col gap-1 text-xs">
                {briefing.tasks
                  .filter((t) => t.status === "done")
                  .map((t, i) => (
                    <li key={i}>
                      ✓ {t.title}
                      {t.assignee_name ? ` · ${t.assignee_name}` : ""}
                      {t.completed_at ? ` · ${formatDateTime(t.completed_at)}` : ""}
                    </li>
                  ))}
              </ul>
            )}
          </div>
        </div>
        <div className="px-4 py-3">
          <p className="text-muted-foreground mb-2 text-xs font-medium">
            Knowledge ({briefing.knowledge.filter((k) => k.outcome === "handed_over").length} handed
            over, {briefing.knowledge.filter((k) => k.outcome === "missing").length} missing)
          </p>
          {briefing.knowledge.length === 0 ? (
            <p className="text-muted-foreground text-xs">No knowledge handover was recorded.</p>
          ) : (
            <ul className="flex flex-col gap-1 text-xs">
              {briefing.knowledge.map((k, i) => (
                <li key={i}>
                  {k.outcome === "handed_over" ? "✓ Handed over" : "! Missing"} ·{" "}
                  {k.responsibility_name}
                  {k.title ? (
                    k.url ? (
                      <>
                        {": "}
                        <a href={k.url} target="_blank" rel="noreferrer" className="underline">
                          {k.title}
                        </a>
                      </>
                    ) : (
                      `: ${k.title}`
                    )
                  ) : null}
                  {k.note ? <span className="text-muted-foreground"> · {k.note}</span> : null}
                </li>
              ))}
            </ul>
          )}
          {briefing.exceptions ? (
            <p className="mt-2 text-xs text-amber-800 dark:text-amber-300">
              {briefing.exceptions} responsibilit{briefing.exceptions === 1 ? "y was" : "ies were"}{" "}
              not covered (recorded exception).
            </p>
          ) : null}
        </div>
        {briefing.notes.length > 0 ? (
          <div className="px-4 py-3">
            <p className="text-muted-foreground mb-2 text-xs font-medium">Notes captured</p>
            <ul className="flex flex-col gap-2">
              {briefing.notes.map((n) => (
                <li key={n.id} className="text-sm">
                  <span className="text-muted-foreground text-xs">
                    {n.actor_name} · {formatDateTime(n.occurred_at)}
                  </span>
                  <p className="whitespace-pre-line">{n.body}</p>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </Section>
  );
}
