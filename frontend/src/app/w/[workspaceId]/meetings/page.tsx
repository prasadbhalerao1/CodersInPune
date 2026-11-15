import { MessagesSquare } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { ActionForm, inputClass, SubmitButton } from "@/components/action-form";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { Explain } from "@/components/explain";
import { EmptyState, formatDateTime, PageHeader, Section } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { attempt } from "@/lib/attempt";
import { api } from "@/lib/relay-api";
import { cn } from "@/lib/utils";

import { createMeetingAction } from "./actions";
import { KIND_LABEL } from "./kinds";
import { TranscriptField } from "./transcript-field";

export const metadata: Metadata = { title: "Meetings" };

export default async function MeetingsPage({ params }: PageProps<"/w/[workspaceId]/meetings">) {
  const { workspaceId } = await params;
  const [meetings, responsibilities, cases] = await Promise.all([
    attempt(api.meetings(workspaceId)),
    attempt(api.listResponsibilities(workspaceId, { limit: "200" })),
    attempt(api.listCases(workspaceId, { limit: "100" })),
  ]);
  if (!meetings.ok) return <ApiErrorNotice error={meetings.error} />;
  const base = `/w/${workspaceId}/meetings`;

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader
        title={
          <span className="flex items-center gap-2">
            Meetings <Explain what="meetings" align="start" />
          </span>
        }
      />
      <div className="grid gap-8 p-6 xl:grid-cols-[minmax(0,1fr)_28rem]">
        <Section
          title="Past meetings"
          description="What each meeting decided, who agreed to do what, and what is still open."
        >
          {meetings.data.length === 0 ? (
            <EmptyState
              title="No meetings yet"
              description="Paste the notes or transcript of a meeting. Relay pulls out decisions, actions, open questions and risks, each linked to the line it came from."
            />
          ) : (
            <ul className="divide-y rounded-lg border">
              {meetings.data.map((m) => (
                <li key={m.id}>
                  <Link
                    href={`${base}/${m.id}`}
                    className="hover:bg-muted/40 flex flex-wrap items-center gap-3 px-4 py-3 text-sm transition-colors"
                  >
                    <MessagesSquare aria-hidden className="text-muted-foreground size-4" />
                    <span className="min-w-0 flex-1 truncate font-medium">{m.title}</span>
                    {(["decision", "action", "question", "risk"] as const).map((k) =>
                      m.counts[k] ? (
                        <span key={k} className="text-muted-foreground text-xs tabular-nums">
                          {m.counts[k]} {KIND_LABEL[k].toLowerCase()}
                        </span>
                      ) : null,
                    )}
                    {m.pending ? <Badge tone="warning">{m.pending} to review</Badge> : null}
                    <span className="text-muted-foreground text-xs">
                      {formatDateTime(m.held_at)}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Section>

        <Section title="Add a meeting" description="Nothing changes until you accept an item.">
          <ActionForm
            action={createMeetingAction.bind(null, workspaceId)}
            className="flex flex-col gap-3"
          >
            <label className="flex flex-col gap-1.5 text-sm font-medium">
              Title
              <input name="title" required maxLength={200} className={inputClass} />
            </label>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="flex flex-col gap-1.5 text-sm font-medium">
                Date
                <input name="held_at" type="date" className={inputClass} />
              </label>
              <label className="flex flex-col gap-1.5 text-sm font-medium">
                Responsibility
                <select name="responsibility_id" defaultValue="" className={inputClass}>
                  <option value="">None</option>
                  {(responsibilities.ok ? responsibilities.data : []).map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.name}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <label className="flex flex-col gap-1.5 text-sm font-medium">
              Case (accepted actions become its tasks)
              <select name="case_id" defaultValue="" className={cn(inputClass)}>
                <option value="">None</option>
                {(cases.ok ? cases.data : [])
                  .filter((c) => c.status !== "completed" && c.status !== "cancelled")
                  .map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.title}
                    </option>
                  ))}
              </select>
            </label>
            <TranscriptField />
            <SubmitButton pendingLabel="Reading the meeting…">
              Extract decisions & actions
            </SubmitButton>
          </ActionForm>
        </Section>
      </div>
    </div>
  );
}
