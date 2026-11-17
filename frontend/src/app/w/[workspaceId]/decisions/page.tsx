import { BookOpen, Bot, MessagesSquare } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { ApiErrorNotice } from "@/components/api-error-notice";
import { Explain } from "@/components/explain";
import { Filtered, FilterTabs } from "@/components/filter-tabs";
import { EmptyState, formatDateTime, PageHeader } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { attempt } from "@/lib/attempt";
import { api } from "@/lib/relay-api";
import type { DecisionEntry } from "@/lib/types";

export const metadata: Metadata = { title: "Decision log" };

const ORIGIN = {
  knowledge: { label: "Recorded decision", icon: BookOpen },
  meeting: { label: "From a meeting", icon: MessagesSquare },
  analysis: { label: "Reconstructed by analysis", icon: Bot },
} as const;

const STATUS: Record<string, { label: string; tone: "neutral" | "warning" | "muted" }> = {
  recorded: { label: "Recorded", tone: "neutral" },
  accepted: { label: "Confirmed", tone: "neutral" },
  proposed: { label: "Awaiting review", tone: "warning" },
  unreviewed: { label: "Unreviewed", tone: "warning" },
  superseded: { label: "Superseded", tone: "muted" },
};

export default async function DecisionsPage({ params }: PageProps<"/w/[workspaceId]/decisions">) {
  const { workspaceId } = await params;
  const log = await attempt(api.decisions(workspaceId));
  if (!log.ok) return <ApiErrorNotice error={log.error} />;
  const base = `/w/${workspaceId}`;
  const counts = {
    all: log.data.length,
    knowledge: log.data.filter((d) => d.origin === "knowledge").length,
    meeting: log.data.filter((d) => d.origin === "meeting").length,
    analysis: log.data.filter((d) => d.origin === "analysis").length,
  };

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader
        title={
          <span className="flex items-center gap-2">
            Decision log <Explain what="decision_log" align="start" />
          </span>
        }
        description="Every decision Relay knows about, with where it was made, so a successor knows what is settled and why."
      />
      <div className="flex flex-col gap-4 p-4 md:p-6">
        {log.data.length === 0 ? (
          <EmptyState
            title="No decisions yet"
            description="Decisions appear here when they are recorded as decision knowledge, accepted from a meeting, or reconstructed by a case analysis."
          />
        ) : (
          <FilterTabs
            label="Decision source"
            initial="all"
            filters={[
              { key: "all", label: "All", count: counts.all },
              { key: "knowledge", label: "Recorded", count: counts.knowledge },
              { key: "meeting", label: "Meetings", count: counts.meeting },
              { key: "analysis", label: "Analyses", count: counts.analysis },
            ]}
          >
            <Filtered when={["all"]}>
              <Timeline entries={log.data} base={base} />
            </Filtered>
            {(["knowledge", "meeting", "analysis"] as const).map((o) => (
              <Filtered key={o} when={[o]}>
                <Timeline entries={log.data.filter((d) => d.origin === o)} base={base} />
              </Filtered>
            ))}
          </FilterTabs>
        )}
      </div>
    </div>
  );
}

function Timeline({ entries, base }: { entries: DecisionEntry[]; base: string }) {
  if (!entries.length)
    return <p className="text-muted-foreground text-sm">None from this source.</p>;
  return (
    <ol className="relative ml-3 flex flex-col gap-4 border-l pl-6">
      {entries.map((d) => {
        const origin = ORIGIN[d.origin];
        const status = STATUS[d.status] ?? STATUS.recorded;
        const href = d.knowledge_id
          ? `${base}/knowledge/${d.knowledge_id}`
          : d.meeting_id
            ? `${base}/meetings/${d.meeting_id}${d.lines[0] ? `#L${d.lines[0]}` : ""}`
            : d.case_id
              ? `${base}/cases/${d.case_id}/analysis`
              : null;
        return (
          <li key={d.id} className="relative">
            <span className="bg-background absolute top-1 -left-[33px] flex size-[18px] items-center justify-center rounded-full border">
              <origin.icon aria-hidden className="text-primary size-3" />
            </span>
            <div className="bg-card rounded-lg border px-4 py-3 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <p className="min-w-0 flex-1 font-medium">{d.text}</p>
                <Badge tone={status.tone}>{status.label}</Badge>
              </div>
              {d.rationale ? (
                <p className="text-muted-foreground mt-1">Why: {d.rationale}</p>
              ) : null}
              <p className="text-muted-foreground mt-1.5 flex flex-wrap gap-x-3 text-xs">
                <span>{d.decided_at ? formatDateTime(d.decided_at) : "Date unknown"}</span>
                <span>{origin.label}</span>
                {d.meeting_title ? <span>“{d.meeting_title}”</span> : null}
                {d.responsibility_name ? <span>{d.responsibility_name}</span> : null}
                {href ? (
                  <Link href={href} className="text-primary hover:underline">
                    Open source
                  </Link>
                ) : null}
              </p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
