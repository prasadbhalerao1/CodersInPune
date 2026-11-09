import Link from "next/link";

import { formatDateTime, Section } from "@/components/page";
import { CriticalityBadge, ROLE_LABEL } from "@/components/ui/badge";
import type { CaseDetail, ScopeItemView } from "@/lib/types";

function Line({ when, who, note }: { when: string; who: string; note?: string }) {
  return (
    <li className="grid grid-cols-[7.5rem_1fr] gap-3 text-sm">
      <span className="text-muted-foreground text-xs leading-5">{when}</span>
      <span>
        <span className="font-medium">{who}</span>
        {note ? <span className="text-muted-foreground"> · {note}</span> : null}
      </span>
    </li>
  );
}

function plan(c: CaseDetail, item: ScopeItemView) {
  const owner = item.current_owner_name ?? "Nobody";
  const role = ROLE_LABEL[item.role].toLowerCase();
  const recipient = item.recipient?.name;
  const start = formatDateTime(c.starts_at);
  const end = c.ends_at ? formatDateTime(c.ends_at) : null;
  const closed = c.status === "completed" || c.status === "cancelled";

  if (item.state === "excepted" || item.exception_reason) {
    return [
      <Line key="now" when="Now" who={owner} note={`stays ${role}`} />,
      <Line
        key="exc"
        when="Exception"
        who="No handover"
        note={item.exception_reason ?? "Recorded exception"}
      />,
    ];
  }
  if (c.status === "cancelled") {
    return [<Line key="now" when="Now" who={owner} note="unchanged; the case was cancelled" />];
  }
  if (c.case_type === "coverage") {
    if (!recipient) {
      return [
        <Line key="now" when="Now" who={owner} note={role} />,
        <Line key="gap" when={`${start} →`} who="Nobody covers yet" note="choose a recipient" />,
      ];
    }
    if (item.state === "applied" && !closed) {
      return [
        <Line key="now" when="Now" who={recipient} note={`covering until ${end}`} />,
        <Line key="keep" when="Meanwhile" who={owner} note={`remains ${role}, away`} />,
        <Line
          key="after"
          when={end ? `After ${end}` : "After"}
          who={owner}
          note="back in charge"
        />,
      ];
    }
    if (closed) {
      return [
        <Line key="was" when="Covered" who={recipient} note={`${start} → ${end ?? "end"}`} />,
        <Line key="now" when="Now" who={owner} note={`${role} again`} />,
      ];
    }
    return [
      <Line key="now" when="Now" who={owner} note={role} />,
      <Line key="cover" when={`From ${start}`} who={recipient} note={`covers until ${end}`} />,
      <Line key="after" when={end ? `After ${end}` : "After"} who={owner} note="back in charge" />,
    ];
  }
  // transfer and departure: a permanent change on the effective date
  if (!recipient) {
    return [
      <Line key="now" when="Now" who={owner} note={role} />,
      <Line
        key="gap"
        when={`From ${start}`}
        who="No recipient yet"
        note="choose one or record an exception"
      />,
    ];
  }
  if (item.state === "applied") {
    return [<Line key="now" when="Now" who={recipient} note={`${role} since ${start}`} />];
  }
  return [
    <Line key="now" when="Now" who={owner} note={role} />,
    <Line
      key="next"
      when={`From ${start}`}
      who={recipient}
      note={`becomes ${role} on execution`}
    />,
  ];
}

/** Answers, per responsibility: who owns it now, and who will own it next. */
export function OwnershipPlan({
  workspaceId,
  detail: c,
}: {
  workspaceId: string;
  detail: CaseDetail;
}) {
  if (!c.scope.length) return null;
  return (
    <Section
      title="Ownership plan"
      description={
        c.case_type === "coverage"
          ? "Temporary cover never replaces the owner; ownership returns automatically when cover ends."
          : "Ownership changes when the approved plan is executed."
      }
    >
      <ul className="divide-y rounded-lg border">
        {c.scope.map((item) => (
          <li key={item.id} className="flex flex-col gap-2 px-4 py-3">
            <div className="flex flex-wrap items-center gap-2">
              <Link
                href={`/w/${workspaceId}/responsibilities/${item.responsibility_id}`}
                className="text-sm font-medium hover:underline"
              >
                {item.responsibility_name}
              </Link>
              <CriticalityBadge value={item.criticality} />
            </div>
            <ol className="flex flex-col gap-1">{plan(c, item)}</ol>
          </li>
        ))}
      </ul>
    </Section>
  );
}

/** What is blocking the case and who needs to act, derived from recorded state only. */
export function Blockers({ detail: c }: { detail: CaseDetail }) {
  if (c.status === "completed" || c.status === "cancelled") return null;
  const now = new Date().getTime(); // server component: rendered per request
  const items: string[] = [];
  const unplanned = c.scope.filter((s) => !s.recipient && !s.exception_reason).length;
  if (c.status === "draft" && unplanned) {
    items.push(
      `${unplanned} responsibilit${unplanned === 1 ? "y needs" : "ies need"} a recipient or an exception (coordinator)`,
    );
  }
  if (c.status === "planning" && !c.approved) items.push("Approval from an owner or admin");
  const blocked = c.criteria.filter((x) => x.status === "blocked").length;
  const pending = c.criteria.filter((x) => x.mandatory && x.status === "pending").length;
  if (c.status === "executing" && blocked) items.push(`${blocked} readiness check(s) blocked`);
  if (c.status === "executing" && pending)
    items.push(`${pending} required readiness check(s) pending`);
  const overdue = c.tasks.filter(
    (t) => t.status === "open" && t.due_at && new Date(t.due_at).getTime() < now,
  );
  if (overdue.length) {
    const who = [...new Set(overdue.map((t) => t.assignee_name ?? "unassigned"))].join(", ");
    items.push(`${overdue.length} overdue task(s): ${who}`);
  }
  if (!items.length) return null;
  return (
    <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
      <span className="font-medium">Waiting on:</span>
      {items.map((i) => (
        <span
          key={i}
          className="rounded-md border border-amber-600/25 bg-amber-50 px-2 py-0.5 text-amber-900 dark:bg-amber-950/30 dark:text-amber-200"
        >
          {i}
        </span>
      ))}
    </div>
  );
}
