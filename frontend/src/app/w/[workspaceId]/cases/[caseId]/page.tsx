import Link from "next/link";

import { ActionForm, inputClass, SubmitButton } from "@/components/action-form";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { PageHeader } from "@/components/page";
import { CaseStatusBadge, EmergencyBadge } from "@/components/ui/badge";
import { attempt } from "@/lib/attempt";
import { api } from "@/lib/relay-api";
import type { CaseDetail } from "@/lib/types";

import { addCommentAction, caseCommandAction } from "../actions";
import { ActivityPanel, BriefingSection, EmergencyBanner, EmergencyControl } from "./collaboration";
import { CommentComposer } from "./comment-composer";
import { ImpactPanel } from "./impact";
import { KnowledgeHandover } from "./knowledge-handover";
import { Blockers, OwnershipPlan } from "./ownership-plan";
import { ApprovalPanel, ReadinessSection, ScopeSection, TasksSection } from "./sections";
import {
  BlockersPanel,
  CASE_TABS,
  CaseDetailsForm,
  CaseFacts,
  CaseProgress,
  CaseTabs,
  type CaseTab,
  DeclinePanel,
  DuplicateNotice,
  nextStep,
  PeoplePanel,
  SplitPanel,
  StatusControls,
  StatusHistory,
} from "./workflow";

const isTab = (value: unknown): value is CaseTab =>
  typeof value === "string" && CASE_TABS.some(([tab]) => tab === value);

export default async function CasePage({
  params,
  searchParams,
}: PageProps<"/w/[workspaceId]/cases/[caseId]">) {
  const [{ workspaceId, caseId }, query] = await Promise.all([params, searchParams]);
  const tab: CaseTab = isTab(query.tab) ? query.tab : "overview";
  // Each tab loads only what it shows.
  const needs = {
    people: tab === "overview" || tab === "people",
    members: ["overview", "tasks", "people", "activity"].includes(tab),
  };
  const [detail, people, teams, members, responsibilities] = await Promise.all([
    attempt(api.getCase(workspaceId, caseId)),
    needs.people ? attempt(api.listPeople(workspaceId)) : null,
    tab === "overview" ? attempt(api.listTeams(workspaceId)) : null,
    needs.members ? attempt(api.members(workspaceId)) : null,
    tab === "overview" ? attempt(api.listResponsibilities(workspaceId)) : null,
  ]);
  if (!detail.ok) return <ApiErrorNotice error={detail.error} />;
  for (const r of [people, teams, members, responsibilities]) {
    if (r && !r.ok) return <ApiErrorNotice error={r.error} />;
  }
  const c = detail.data;
  const ctx = { workspaceId, caseId, detail: c };
  const can = (action: CaseDetail["allowed_actions"][number]) => c.allowed_actions.includes(action);
  const command = (name: "submit" | "execute" | "complete" | "cancel") =>
    caseCommandAction.bind(null, workspaceId, caseId, name);
  const memberList = members?.ok ? members.data : [];
  const openBlockers = c.blockers.filter((b) => !b.resolved_at).length;
  const sodOnComplete =
    c.critical &&
    can("complete") &&
    c.approvals.some((a) => a.current && a.decision === "approved");

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
            {can("complete") && !sodOnComplete ? (
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
      <div className="flex flex-col gap-2 px-6 pt-3">
        <CaseProgress detail={c} />
        <p className="text-muted-foreground text-sm" role="status">
          {nextStep(c)}
        </p>
        <Blockers detail={c} />
      </div>
      <CaseTabs
        workspaceId={workspaceId}
        caseId={caseId}
        current={tab}
        counts={{
          tasks: c.tasks.filter((t) => t.status === "open").length,
          overview: openBlockers,
          approvals: c.status === "planning" || c.status === "awaiting_review" ? 1 : 0,
        }}
      />
      <div className="grid gap-8 p-6 xl:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="flex min-w-0 flex-col gap-8">
          {tab === "overview" ? (
            <>
              <DuplicateNotice detail={c} workspaceId={workspaceId} />
              <DeclinePanel {...ctx} />
              <StatusControls {...ctx} />
              {sodOnComplete ? (
                <ActionForm action={command("complete")} className="rounded-lg border p-4 text-sm">
                  <p className="font-medium">Verify and complete</p>
                  <p className="text-muted-foreground text-xs">
                    This case includes critical responsibilities: the verifier should be someone who
                    neither started nor approved it. If that isn&apos;t possible, record why.
                  </p>
                  <input
                    name="sod_exception_reason"
                    maxLength={4000}
                    placeholder="Exception reason (only if you started or approved this case)"
                    aria-label="Separation-of-duties exception"
                    className={inputClass}
                  />
                  <SubmitButton size="sm" pendingLabel="Completing…">
                    Complete case
                  </SubmitButton>
                </ActionForm>
              ) : null}
              <BlockersPanel {...ctx} members={memberList} />
              <OwnershipPlan workspaceId={workspaceId} detail={c} />
              <ScopeSection
                {...ctx}
                people={people?.ok ? people.data : []}
                teams={teams?.ok ? teams.data : []}
                responsibilities={responsibilities?.ok ? responsibilities.data : []}
              />
              <SplitPanel {...ctx} />
            </>
          ) : null}
          {tab === "impact" ? <ImpactTab {...ctx} /> : null}
          {tab === "knowledge" ? <KnowledgeTab {...ctx} /> : null}
          {tab === "tasks" ? (
            <>
              <TasksSection {...ctx} members={memberList} />
              <ReadinessSection {...ctx} />
            </>
          ) : null}
          {tab === "people" ? (
            <PeopleTab {...ctx} members={memberList} people={people?.ok ? people.data : []} />
          ) : null}
          {tab === "approvals" ? <ApprovalPanel {...ctx} /> : null}
          {tab === "activity" ? (
            <>
              <StatusHistory detail={c} />
              <ActivityTab {...ctx} members={memberList} />
            </>
          ) : null}
        </div>
        <aside className="flex flex-col gap-6">
          <CaseFacts detail={c} workspaceId={workspaceId} />
          {c.reason ? (
            <p className="text-muted-foreground text-sm whitespace-pre-line">{c.reason}</p>
          ) : null}
          {tab === "overview" ? (
            <>
              <CaseDetailsForm {...ctx} members={memberList} />
              <EmergencyControl {...ctx} />
            </>
          ) : null}
          {tab !== "approvals" && (can("decide") || c.approval_due_at) ? (
            <p className="text-sm">
              <Link
                href={`/w/${workspaceId}/cases/${caseId}?tab=approvals`}
                className="font-medium underline-offset-2 hover:underline"
              >
                {can("decide") ? "Review the plan for approval →" : "Approvals →"}
              </Link>
            </p>
          ) : null}
        </aside>
      </div>
    </div>
  );
}

type Ctx = { workspaceId: string; caseId: string; detail: CaseDetail };

async function ImpactTab({ workspaceId, caseId }: Ctx) {
  const impact = await attempt(api.caseImpact(workspaceId, caseId));
  if (!impact.ok) return <ApiErrorNotice error={impact.error} />;
  return <ImpactPanel workspaceId={workspaceId} impact={impact.data} />;
}

async function KnowledgeTab({ workspaceId, caseId, detail: c }: Ctx) {
  const knowledge = await attempt(api.caseKnowledge(workspaceId, caseId));
  if (!knowledge.ok) return <ApiErrorNotice error={knowledge.error} />;
  const briefing =
    c.case_type === "coverage" && (c.status === "executing" || c.status === "completed")
      ? await attempt(api.caseBriefing(workspaceId, caseId))
      : null;
  return (
    <>
      <KnowledgeHandover
        workspaceId={workspaceId}
        caseId={caseId}
        entries={knowledge.data}
        canRecord={c.allowed_actions.includes("add_task")}
      />
      {briefing?.ok ? <BriefingSection briefing={briefing.data} /> : null}
      <p className="text-muted-foreground text-sm">
        Gaps only the person handing over can fill go in the{" "}
        <Link
          href={`/w/${workspaceId}/cases/${caseId}/interview`}
          className="text-foreground font-medium underline-offset-2 hover:underline"
        >
          interview
        </Link>
        ; the recipient&apos;s view of everything is the{" "}
        <Link
          href={`/w/${workspaceId}/cases/${caseId}/capsules`}
          className="text-foreground font-medium underline-offset-2 hover:underline"
        >
          handover capsule
        </Link>
        .
      </p>
    </>
  );
}

async function PeopleTab({
  members,
  people,
  ...ctx
}: Ctx & {
  members: Awaited<ReturnType<typeof api.members>>;
  people: Awaited<ReturnType<typeof api.listPeople>>;
}) {
  const participants = await attempt(api.caseParticipants(ctx.workspaceId, ctx.caseId));
  if (!participants.ok) return <ApiErrorNotice error={participants.error} />;
  return (
    <PeoplePanel {...ctx} participants={participants.data} members={members} people={people} />
  );
}

async function ActivityTab({
  workspaceId,
  caseId,
  detail: c,
  members,
}: Ctx & { members: Awaited<ReturnType<typeof api.members>> }) {
  const activity = await attempt(api.caseActivity(workspaceId, caseId));
  if (!activity.ok) return <ApiErrorNotice error={activity.error} />;
  const mentionable = members
    .filter((m) => m.status === "active")
    .map((m) => ({ user_id: m.user_id, name: m.name }));
  return (
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
  );
}
