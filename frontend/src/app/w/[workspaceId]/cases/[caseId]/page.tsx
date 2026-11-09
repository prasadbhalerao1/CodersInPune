import Link from "next/link";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { ActionForm, SubmitButton } from "@/components/action-form";
import { formatDateTime, PageHeader } from "@/components/page";
import { CaseStatusBadge, EmergencyBadge } from "@/components/ui/badge";
import { attempt } from "@/lib/attempt";
import { api } from "@/lib/relay-api";
import type { CaseDetail } from "@/lib/types";
import { cn } from "@/lib/utils";

import { addCommentAction, caseCommandAction } from "../actions";
import { CASE_TYPES } from "../labels";
import { ActivityPanel, BriefingSection, EmergencyBanner, EmergencyControl } from "./collaboration";
import { CommentComposer } from "./comment-composer";
import { KnowledgeHandover } from "./knowledge-handover";
import { Blockers, OwnershipPlan } from "./ownership-plan";
import { ApprovalPanel, ReadinessSection, ScopeSection, TasksSection } from "./sections";

const STEPS = [
  { status: "draft", label: "Scope" },
  { status: "planning", label: "Plan & approve" },
  { status: "executing", label: "Hand over" },
  { status: "completed", label: "Complete" },
] as const;

function nextStep(c: CaseDetail): string {
  switch (c.status) {
    case "draft":
      return "Choose a recipient (or record an exception) for every responsibility, then submit.";
    case "planning":
      return c.approved
        ? "Approved. Execute to apply the ownership changes."
        : "Waiting for approval of the current plan.";
    case "executing":
      return c.readiness_met < c.readiness_total
        ? `Readiness ${c.readiness_met}/${c.readiness_total}. Resolve the remaining checks, then complete.`
        : "Readiness is complete. Complete the case to close it.";
    case "completed":
      return c.outcome === "completed_with_exceptions"
        ? "Completed with recorded exceptions."
        : "Completed.";
    case "cancelled":
      return "Cancelled. No ownership was changed.";
  }
}

export default async function CasePage({ params }: PageProps<"/w/[workspaceId]/cases/[caseId]">) {
  const { workspaceId, caseId } = await params;
  const [detail, activity, people, teams, members, responsibilities, knowledge] = await Promise.all(
    [
      attempt(api.getCase(workspaceId, caseId)),
      attempt(api.caseActivity(workspaceId, caseId)),
      attempt(api.listPeople(workspaceId)),
      attempt(api.listTeams(workspaceId)),
      attempt(api.members(workspaceId)),
      attempt(api.listResponsibilities(workspaceId)),
      attempt(api.caseKnowledge(workspaceId, caseId)),
    ],
  );
  if (!detail.ok) return <ApiErrorNotice error={detail.error} />;
  if (!activity.ok) return <ApiErrorNotice error={activity.error} />;
  if (!people.ok) return <ApiErrorNotice error={people.error} />;
  if (!teams.ok) return <ApiErrorNotice error={teams.error} />;
  if (!members.ok) return <ApiErrorNotice error={members.error} />;
  if (!responsibilities.ok) return <ApiErrorNotice error={responsibilities.error} />;

  const c = detail.data;
  const can = (action: CaseDetail["allowed_actions"][number]) => c.allowed_actions.includes(action);
  const command = (name: "submit" | "execute" | "complete" | "cancel") =>
    caseCommandAction.bind(null, workspaceId, caseId, name);
  const reached = STEPS.findIndex((s) => s.status === c.status);
  const ctx = { workspaceId, caseId, detail: c };
  const briefing =
    c.case_type === "coverage" && (c.status === "executing" || c.status === "completed")
      ? await attempt(api.caseBriefing(workspaceId, caseId))
      : null;
  const mentionable = members.data
    .filter((m) => m.status === "active")
    .map((m) => ({ user_id: m.user_id, name: m.name }));

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader
        title={c.title}
        actions={
          <>
            {c.emergency ? <EmergencyBadge /> : null}
            <CaseStatusBadge value={c.status} />
            {can("cancel") ? (
              <ActionForm action={command("cancel")}>
                <SubmitButton
                  variant="ghost"
                  size="sm"
                  pendingLabel="…"
                  confirm="Cancel this case? Planned ownership changes won't be applied."
                >
                  Cancel case
                </SubmitButton>
              </ActionForm>
            ) : null}
            {can("submit") ? (
              <ActionForm action={command("submit")}>
                <SubmitButton size="sm" pendingLabel="Submitting…">
                  Submit for approval
                </SubmitButton>
              </ActionForm>
            ) : null}
            {can("execute") ? (
              <ActionForm action={command("execute")}>
                <SubmitButton size="sm" pendingLabel="Executing…">
                  Execute handover
                </SubmitButton>
              </ActionForm>
            ) : null}
            {can("complete") ? (
              <ActionForm action={command("complete")}>
                <SubmitButton size="sm" pendingLabel="Completing…">
                  {c.case_type === "coverage" && c.ends_at && new Date(c.ends_at) > new Date()
                    ? "End coverage early"
                    : "Complete case"}
                </SubmitButton>
              </ActionForm>
            ) : null}
          </>
        }
      />
      <EmergencyBanner detail={c} />
      <div className="border-b px-6 py-3">
        <ol className="flex flex-wrap items-center gap-x-6 gap-y-2 text-xs" aria-label="Progress">
          {STEPS.map((step, i) => {
            const done = c.status === "completed" || (reached >= 0 && i < reached);
            const current = i === reached && c.status !== "completed";
            return (
              <li
                key={step.status}
                className={cn(
                  "flex items-center gap-2",
                  !done && !current && "text-muted-foreground",
                )}
              >
                <span
                  aria-hidden
                  className={cn(
                    "grid size-5 place-items-center rounded-full border text-[10px] font-medium",
                    done && "bg-foreground text-background border-foreground",
                    current && "border-foreground",
                  )}
                >
                  {done ? "✓" : i + 1}
                </span>
                <span className={current ? "font-medium" : undefined}>{step.label}</span>
              </li>
            );
          })}
        </ol>
        <p className="text-muted-foreground mt-2 text-sm" role="status">
          {nextStep(c)}
        </p>
        <Blockers detail={c} />
        {briefing?.ok ? (
          <p className="mt-2 text-sm">
            <Link
              href={`/w/${workspaceId}/cases/${caseId}/briefing`}
              className="font-medium underline-offset-2 hover:underline"
            >
              {c.status === "completed"
                ? "Open the return briefing →"
                : "Review the return briefing before cover ends →"}
            </Link>
          </p>
        ) : null}
      </div>
      <div className="grid gap-8 p-6 xl:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="flex min-w-0 flex-col gap-8">
          <OwnershipPlan workspaceId={workspaceId} detail={c} />
          <ScopeSection
            {...ctx}
            people={people.data}
            teams={teams.data}
            responsibilities={responsibilities.data}
          />
          <TasksSection {...ctx} members={members.data} />
          <ReadinessSection {...ctx} />
          {knowledge.ok ? (
            <KnowledgeHandover
              workspaceId={workspaceId}
              caseId={caseId}
              entries={knowledge.data}
              canRecord={c.allowed_actions.includes("add_task")}
            />
          ) : null}
          {briefing?.ok ? <BriefingSection briefing={briefing.data} /> : null}
          <ActivityPanel
            activity={activity.data}
            composer={
              c.allowed_actions.includes("comment") ? (
                <CommentComposer
                  action={addCommentAction.bind(null, workspaceId, caseId)}
                  members={mentionable}
                />
              ) : undefined
            }
          />
        </div>
        <aside className="flex flex-col gap-6">
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 rounded-lg border p-4 text-sm">
            <dt className="text-muted-foreground">Playbook</dt>
            <dd>{CASE_TYPES[c.case_type].label}</dd>
            {c.affected_person_name ? (
              <>
                <dt className="text-muted-foreground">Person</dt>
                <dd>{c.affected_person_name}</dd>
              </>
            ) : null}
            <dt className="text-muted-foreground">
              {c.case_type === "coverage" ? "From" : "Effective"}
            </dt>
            <dd>{formatDateTime(c.starts_at)}</dd>
            {c.ends_at ? (
              <>
                <dt className="text-muted-foreground">Until</dt>
                <dd>{formatDateTime(c.ends_at)}</dd>
              </>
            ) : null}
            <dt className="text-muted-foreground">Coordinator</dt>
            <dd>{c.coordinator_name ?? "—"}</dd>
            <dt className="text-muted-foreground">Plan version</dt>
            <dd className="tabular-nums">v{c.plan_version}</dd>
          </dl>
          {c.reason ? (
            <p className="text-muted-foreground text-sm whitespace-pre-line">{c.reason}</p>
          ) : null}
          <ApprovalPanel {...ctx} />
          <EmergencyControl {...ctx} />
        </aside>
      </div>
    </div>
  );
}
