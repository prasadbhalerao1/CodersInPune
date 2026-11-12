import { ArrowRight, CheckCircle2, History, ListChecks, MessageCircleQuestion } from "lucide-react";
import Link from "next/link";

import { formatDateTime } from "@/components/page";
import { Badge, CaseStatusBadge } from "@/components/ui/badge";
import type { CapsuleView, CaseDetail } from "@/lib/types";

// What the recipient does once they have acknowledged the handover: the case's state,
// their own open tasks, what they are taking over (with its history) and where to ask.
export function NextSteps({
  workspaceId,
  capsule,
  detail,
}: {
  workspaceId: string;
  capsule: CapsuleView;
  detail: CaseDetail;
}) {
  const base = `/w/${workspaceId}`;
  const caseHref = `${base}/cases/${detail.id}`;
  const tasks = detail.tasks.filter(
    (t) => t.status === "open" && t.assignee_user_id === capsule.recipient_user_id,
  );
  const scope = detail.scope.filter((s) => !s.hidden);
  const mine = scope.filter((s) => s.recipient?.name === capsule.recipient_name);
  const taking = mine.length > 0 ? mine : scope;
  const executed = detail.status === "completed";

  return (
    <section
      aria-labelledby="next-steps"
      className="motion-page border-primary/25 bg-primary/[0.03] flex flex-col gap-4 rounded-lg border p-4"
    >
      <header className="flex flex-wrap items-center gap-2">
        <CheckCircle2 aria-hidden className="text-primary size-5" />
        <h2 id="next-steps" className="font-semibold">
          Handover acknowledged: your next steps
        </h2>
        <span className="text-muted-foreground text-xs">
          {capsule.recipient_name} · {formatDateTime(capsule.acknowledged_at!)}
        </span>
        <span className="ml-auto">
          <CaseStatusBadge value={detail.status} />
        </span>
      </header>
      <p className="text-muted-foreground text-sm">
        {executed
          ? "Ownership has been transferred. The responsibilities below are now recorded against their new owners."
          : "Ownership moves when the coordinator executes the case. Until then, work through your tasks and ask about anything unclear."}
      </p>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="flex flex-col gap-2">
          <h3 className="flex items-center gap-1.5 text-sm font-medium">
            <ListChecks aria-hidden className="size-4" /> Your open tasks ({tasks.length})
          </h3>
          {tasks.length === 0 ? (
            <p className="text-muted-foreground text-sm">Nothing assigned to you in this case.</p>
          ) : (
            <ul className="bg-card divide-y rounded-md border text-sm">
              {tasks.slice(0, 5).map((t) => (
                <li key={t.id} className="flex items-center gap-2 px-3 py-2">
                  <span className="min-w-0 flex-1 truncate">{t.title}</span>
                  {t.overdue ? <Badge tone="danger">Overdue</Badge> : null}
                  {t.due_at && !t.overdue ? (
                    <span className="text-muted-foreground text-xs">
                      due {formatDateTime(t.due_at)}
                    </span>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
          <Link
            href={`${caseHref}/tasks`}
            className="text-primary text-xs font-medium hover:underline"
          >
            All case tasks <ArrowRight aria-hidden className="inline size-3" />
          </Link>
        </div>

        <div className="flex flex-col gap-2">
          <h3 className="flex items-center gap-1.5 text-sm font-medium">
            <History aria-hidden className="size-4" /> What you are taking over ({taking.length})
          </h3>
          {taking.length === 0 ? (
            <p className="text-muted-foreground text-sm">No responsibilities in this case.</p>
          ) : (
            <ul className="bg-card divide-y rounded-md border text-sm">
              {taking.slice(0, 5).map((s) => (
                <li key={s.id} className="flex items-center gap-2 px-3 py-2">
                  <Link
                    href={`${base}/responsibilities/${s.responsibility_id}`}
                    className="min-w-0 flex-1 truncate font-medium hover:underline"
                  >
                    {s.responsibility_name}
                  </Link>
                  <span className="text-muted-foreground text-xs">
                    {s.state === "applied" ? "transferred" : s.state}
                  </span>
                  <Link
                    href={`${base}/responsibilities/${s.responsibility_id}/timeline`}
                    className="text-primary text-xs font-medium hover:underline"
                  >
                    History
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs font-medium">
        <a
          href="#copilot-heading"
          className="text-primary inline-flex items-center gap-1 hover:underline"
        >
          <MessageCircleQuestion aria-hidden className="size-3.5" /> Ask about this handover
        </a>
        <Link href={`${caseHref}/interview`} className="text-primary hover:underline">
          Open questions from the interview
        </Link>
        <Link href={`${base}/my-work`} className="text-primary hover:underline">
          Go to My work
        </Link>
      </div>
    </section>
  );
}
