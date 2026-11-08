import Link from "next/link";

import { ActionForm, SubmitButton } from "@/components/action-form";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { EmptyState, formatDateTime, PageHeader } from "@/components/page";
import { EmergencyBadge } from "@/components/ui/badge";
import { attempt } from "@/lib/attempt";
import { api } from "@/lib/relay-api";
import type { NotificationView } from "@/lib/types";
import { cn } from "@/lib/utils";

import { markAllReadAction, openNotificationAction } from "./actions";

const CASE_UPDATE: Record<string, string> = {
  approved: "approved the plan",
  rejected: "rejected the plan",
  executing: "applied the ownership changes",
  completed: "completed the case",
  cancelled: "cancelled the case",
  emergency: "marked the case as an emergency",
};

function message(n: NotificationView): string {
  const who = n.actor_name ?? "Someone";
  const task = n.task_title ? `“${n.task_title}”` : "A task";
  switch (n.kind) {
    case "task_assigned":
      return `${who} assigned you ${task}`;
    case "task_due_soon":
      return `${task} is due within a day`;
    case "task_overdue":
      return `${task} is overdue`;
    case "approval_requested":
      return `${who} asked for approval`;
    case "mentioned":
      return `${who} mentioned you`;
    case "case_update":
      return `${who} ${CASE_UPDATE[n.detail ?? ""] ?? "updated the case"}`;
  }
}

export default async function InboxPage({
  params,
  searchParams,
}: PageProps<"/w/[workspaceId]/inbox">) {
  const [{ workspaceId }, query] = await Promise.all([params, searchParams]);
  const unreadOnly = query.show === "unread";
  const inbox = await attempt(
    api.inbox(workspaceId, unreadOnly ? { unread_only: "true" } : undefined),
  );
  if (!inbox.ok) return <ApiErrorNotice error={inbox.error} />;
  const base = `/w/${workspaceId}/inbox`;

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader
        title="Inbox"
        actions={
          inbox.data.unread > 0 ? (
            <ActionForm action={markAllReadAction.bind(null, workspaceId)}>
              <SubmitButton size="sm" variant="ghost" pendingLabel="…">
                Mark all read
              </SubmitButton>
            </ActionForm>
          ) : null
        }
      />
      <div className="flex max-w-3xl flex-col gap-4 p-6">
        <nav aria-label="Filter" className="flex gap-1 text-sm">
          {[
            { href: base, label: "All", current: !unreadOnly },
            {
              href: `${base}?show=unread`,
              label: `Unread${inbox.data.unread ? ` (${inbox.data.unread})` : ""}`,
              current: unreadOnly,
            },
          ].map((f) => (
            <Link
              key={f.href}
              href={f.href}
              aria-current={f.current ? "page" : undefined}
              className={cn(
                "rounded-md px-2.5 py-1",
                f.current
                  ? "bg-foreground/[0.06] font-medium"
                  : "text-muted-foreground hover:bg-muted",
              )}
            >
              {f.label}
            </Link>
          ))}
        </nav>
        {inbox.data.items.length === 0 ? (
          <EmptyState
            title={unreadOnly ? "Nothing unread" : "No notifications yet"}
            description="Assignments, approval requests, mentions, reminders and case updates appear here."
          />
        ) : (
          <ul className="divide-y rounded-lg border">
            {inbox.data.items.map((n) => (
              <li key={n.id}>
                <ActionForm
                  action={openNotificationAction.bind(null, workspaceId, n.id, n.case_id)}
                >
                  <button
                    type="submit"
                    className="hover:bg-muted/40 flex w-full items-start gap-3 px-4 py-3 text-left text-sm"
                  >
                    <span
                      aria-label={n.read_at ? undefined : "Unread"}
                      className={cn(
                        "mt-1.5 size-2 shrink-0 rounded-full",
                        n.read_at ? "bg-transparent" : "bg-sky-600",
                      )}
                    />
                    <span className="min-w-0 flex-1">
                      <span className={cn("block", !n.read_at && "font-medium")}>{message(n)}</span>
                      <span className="text-muted-foreground flex items-center gap-2 text-xs">
                        <span className="truncate">{n.case_title}</span>
                        {n.case_emergency ? <EmergencyBadge /> : null}
                      </span>
                    </span>
                    <time
                      className="text-muted-foreground shrink-0 text-xs"
                      dateTime={n.created_at}
                    >
                      {formatDateTime(n.created_at)}
                    </time>
                  </button>
                </ActionForm>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
