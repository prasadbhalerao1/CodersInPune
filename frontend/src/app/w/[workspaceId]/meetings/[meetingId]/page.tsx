import { Check, ListChecks, RefreshCw, Send, X } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { ActionForm, SubmitButton } from "@/components/action-form";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { formatDateTime, PageHeader } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { attempt } from "@/lib/attempt";
import { api } from "@/lib/relay-api";
import type { MeetingItemView } from "@/lib/types";
import { cn } from "@/lib/utils";

import { shareMeetingToSlackAction } from "../../integrations/slack/actions";
import { reextractMeetingAction, reviewMeetingItemAction } from "../actions";
import { KIND_LABEL } from "../kinds";

export const metadata: Metadata = { title: "Meeting" };

const KIND_TONE = {
  decision: "border-l-sky-500",
  action: "border-l-emerald-500",
  question: "border-l-amber-500",
  risk: "border-l-rose-500",
} as const;

const OUTCOME: Partial<Record<MeetingItemView["kind"], string>> = {
  decision: "Accepting records it as decision knowledge (an ADR) on the responsibility.",
  action: "Accepting adds it as a task on the case, assigned to the person named.",
};

export default async function MeetingPage({
  params,
}: PageProps<"/w/[workspaceId]/meetings/[meetingId]">) {
  const { workspaceId, meetingId } = await params;
  const [meeting, slack] = await Promise.all([
    attempt(api.meeting(workspaceId, meetingId)),
    attempt(api.slack(workspaceId)),
  ]);
  if (!meeting.ok) return <ApiErrorNotice error={meeting.error} />;
  const m = meeting.data;
  const base = `/w/${workspaceId}`;
  const cited = new Set(m.items.filter((i) => i.status !== "dismissed").flatMap((i) => i.lines));

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader
        title={
          <span className="flex min-w-0 items-center gap-2">
            <Link href={`${base}/meetings`} className="text-muted-foreground hover:text-foreground">
              Meetings
            </Link>
            <span className="text-muted-foreground">/</span>
            <span className="truncate">{m.title}</span>
          </span>
        }
        description={`${formatDateTime(m.held_at)} · ${
          m.extract_mode === "ai"
            ? "Read by AI; every item cites the lines it came from"
            : "Read by rules; every item cites the line it came from"
        }`}
        actions={
          m.can_review ? (
            <span className="flex gap-2">
              {slack.ok && slack.data.connected ? (
                <ActionForm action={shareMeetingToSlackAction.bind(null, workspaceId, m.id)}>
                  <SubmitButton size="sm" variant="outline" pendingLabel="Posting…">
                    <Send aria-hidden className="size-3.5" /> Post to #{slack.data.channel}
                  </SubmitButton>
                </ActionForm>
              ) : null}
              <ActionForm action={reextractMeetingAction.bind(null, workspaceId, m.id)}>
                <SubmitButton size="sm" variant="outline" pendingLabel="Reading…">
                  <RefreshCw aria-hidden className="size-3.5" /> Read again
                </SubmitButton>
              </ActionForm>
            </span>
          ) : undefined
        }
      />
      {m.note ? (
        <p role="status" className="text-muted-foreground mx-6 mt-4 text-sm">
          {m.note} Rules found the items below instead.
        </p>
      ) : null}
      <div className="grid gap-8 p-4 md:p-6 xl:grid-cols-2">
        <div className="flex min-w-0 flex-col gap-6">
          {m.items.length === 0 ? (
            <p className="text-muted-foreground text-sm">
              No decisions, actions, questions or risks were found in this meeting.
            </p>
          ) : null}
          {(["decision", "action", "question", "risk"] as const).map((kind) => {
            const items = m.items.filter((i) => i.kind === kind);
            if (!items.length) return null;
            return (
              <section key={kind} aria-labelledby={`k-${kind}`} className="panel-in">
                <h2 id={`k-${kind}`} className="mb-2 flex items-center gap-2 font-semibold">
                  {KIND_LABEL[kind]}
                  <span className="text-muted-foreground text-sm tabular-nums">{items.length}</span>
                </h2>
                {OUTCOME[kind] && m.can_review ? (
                  <p className="text-muted-foreground mb-2 text-xs">
                    {OUTCOME[kind]}
                    {kind === "decision" && !m.responsibility_id
                      ? " No responsibility is linked, so it is only marked accepted."
                      : ""}
                    {kind === "action" && !m.case_id
                      ? " No case is linked, so it is only marked accepted."
                      : ""}
                  </p>
                ) : null}
                <ul className="flex flex-col gap-2">
                  {items.map((item) => (
                    <Item
                      key={item.id}
                      item={item}
                      workspaceId={workspaceId}
                      canReview={m.can_review}
                      base={base}
                    />
                  ))}
                </ul>
              </section>
            );
          })}
        </div>
        <section aria-labelledby="transcript" className="min-w-0">
          <h2 id="transcript" className="mb-2 font-semibold">
            Transcript
          </h2>
          <ol className="bg-card max-h-[75vh] overflow-auto rounded-lg border py-2 font-mono text-[13px] leading-relaxed">
            {m.lines.map((line, i) => (
              <li
                key={i}
                id={`L${i + 1}`}
                className={cn(
                  "flex scroll-mt-24 gap-3 px-3 transition-colors target:bg-amber-100 dark:target:bg-amber-900/40",
                  cited.has(i + 1) && "bg-primary/[0.06]",
                )}
              >
                <span className="text-muted-foreground w-7 shrink-0 text-right select-none">
                  {i + 1}
                </span>
                <span className="min-w-0 break-words whitespace-pre-wrap">{line || " "}</span>
              </li>
            ))}
          </ol>
        </section>
      </div>
    </div>
  );
}

function Item({
  item,
  workspaceId,
  canReview,
  base,
}: {
  item: MeetingItemView;
  workspaceId: string;
  canReview: boolean;
  base: string;
}) {
  const [target, id] = (item.result_ref ?? "").split(":");
  return (
    <li
      className={cn(
        "bg-card rounded-lg border border-l-4 px-4 py-3 text-sm",
        KIND_TONE[item.kind],
        item.status === "dismissed" && "opacity-60",
      )}
    >
      <p className={cn(item.status === "dismissed" && "line-through")}>{item.text}</p>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
        {item.owner_name ? <Badge>Owner: {item.owner_name}</Badge> : null}
        {item.due_text ? <Badge>Due: {item.due_text}</Badge> : null}
        {item.lines.map((n) => (
          <a
            key={n}
            href={`#L${n}`}
            title={`Show line ${n} of the transcript`}
            className="text-primary bg-primary/10 rounded px-1.5 py-0.5 font-mono hover:underline"
          >
            L{n}
          </a>
        ))}
        <span className="text-muted-foreground">{item.source === "ai" ? "AI" : "Rule"}</span>
        <span className="ml-auto flex items-center gap-1">
          {item.status === "accepted" ? (
            <>
              <Badge>
                <Check aria-hidden className="mr-1 inline size-3" />
                Accepted
              </Badge>
              {target === "knowledge" ? (
                <Link href={`${base}/knowledge/${id}`} className="text-primary hover:underline">
                  View decision
                </Link>
              ) : target === "case" ? (
                <Link
                  href={`${base}/cases/${id}`}
                  className="text-primary inline-flex items-center gap-1 hover:underline"
                >
                  <ListChecks aria-hidden className="size-3.5" /> View task
                </Link>
              ) : null}
            </>
          ) : item.status === "dismissed" ? (
            <Badge tone="muted">Dismissed</Badge>
          ) : canReview ? (
            <>
              <ActionForm
                action={reviewMeetingItemAction.bind(null, workspaceId, item.id, "accept")}
              >
                <SubmitButton size="sm" pendingLabel="…">
                  <Check aria-hidden className="size-3.5" /> Accept
                </SubmitButton>
              </ActionForm>
              <ActionForm
                action={reviewMeetingItemAction.bind(null, workspaceId, item.id, "dismiss")}
              >
                <SubmitButton size="sm" variant="ghost" pendingLabel="…">
                  <X aria-hidden className="size-3.5" /> Dismiss
                </SubmitButton>
              </ActionForm>
            </>
          ) : null}
        </span>
      </div>
    </li>
  );
}
