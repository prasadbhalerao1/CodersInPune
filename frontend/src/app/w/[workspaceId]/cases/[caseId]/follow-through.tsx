import Link from "next/link";

import { formatDateTime, Section } from "@/components/page";
import { Badge, CriticalityBadge } from "@/components/ui/badge";
import type { FollowState, FollowThroughItem, FollowThroughView } from "@/lib/types";

const STATE: Record<
  FollowState,
  { label: string; tone: "danger" | "warning" | "neutral" | "muted" }
> = {
  settled: { label: "Settled", tone: "neutral" },
  settling: { label: "Settling in", tone: "muted" },
  check_in: { label: "Check in", tone: "warning" },
  not_in_place: { label: "New holder not recorded", tone: "danger" },
};

function signals(i: FollowThroughItem) {
  if (i.state === "not_in_place") return "The planned holder has no active ownership of this.";
  const parts = [
    i.reviewed_since ? "reviewed since the handover" : "not reviewed since the handover",
    i.activity_since
      ? `${i.activity_since} recorded event${i.activity_since === 1 ? "" : "s"} since (latest ${formatDateTime(i.last_activity_at!)})`
      : "no recorded activity since",
  ];
  if (i.open_tasks) {
    parts.push(
      `${i.open_tasks} open task${i.open_tasks === 1 ? "" : "s"}${i.overdue_tasks ? `, ${i.overdue_tasks} overdue` : ""}`,
    );
  }
  return parts.join(" · ");
}

/** After execution: did each transfer take hold? Reads the work, never scores the person. */
export function FollowThrough({
  workspaceId,
  view,
}: {
  workspaceId: string;
  view: FollowThroughView;
}) {
  if (!view.applies || view.items.length === 0) return null;
  return (
    <Section
      title="Follow-through"
      description={`${view.settled} of ${view.items.length} handed-over responsibilities have settled. ${view.rule}`}
    >
      <ul className="divide-y rounded-lg border text-sm">
        {view.items.map((i) => (
          <li key={i.scope_item_id} className="flex flex-wrap items-start gap-3 px-4 py-3">
            <span className="min-w-0 flex-1">
              <Link
                href={`/w/${workspaceId}/responsibilities/${i.responsibility_id}`}
                className="font-medium hover:underline"
              >
                {i.responsibility_name}
              </Link>{" "}
              <CriticalityBadge value={i.criticality} />
              <span className="text-muted-foreground block text-xs">
                {i.recipient_name ? `With ${i.recipient_name}` : "No recipient"}
                {i.holder_since ? ` since ${formatDateTime(i.holder_since)}` : ""} · {signals(i)}
              </span>
            </span>
            <Badge tone={STATE[i.state].tone}>{STATE[i.state].label}</Badge>
            {i.state === "check_in" || i.state === "settling" ? (
              <Link
                href={`/w/${workspaceId}/responsibilities/${i.responsibility_id}/timeline`}
                className="text-primary text-xs font-medium hover:underline"
              >
                Memory replay
              </Link>
            ) : null}
          </li>
        ))}
      </ul>
    </Section>
  );
}
