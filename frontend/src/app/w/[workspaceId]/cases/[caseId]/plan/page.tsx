import { Check, Plus } from "lucide-react";
import type { Metadata } from "next";

import { ActionForm, SubmitButton } from "@/components/action-form";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { Explain } from "@/components/explain";
import { formatDateTime } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { attempt } from "@/lib/attempt";
import { api } from "@/lib/relay-api";
import { cn } from "@/lib/utils";

import { addPlanStepAction } from "../ai-actions";
import { CaseAiHeader } from "../ai-nav";

export const metadata: Metadata = { title: "30/60/90 plan" };

const SOURCE = {
  scope: "Scope",
  task: "Open task",
  criterion: "Readiness check",
  case: "Case",
} as const;

const ACCENT = { 30: "bg-sky-500", 60: "bg-amber-500", 90: "bg-emerald-500" } as const;

export default async function PlanPage({
  params,
}: PageProps<"/w/[workspaceId]/cases/[caseId]/plan">) {
  const { workspaceId, caseId } = await params;
  const [caseDetail, plan] = await Promise.all([
    attempt(api.getCase(workspaceId, caseId)),
    attempt(api.plan(workspaceId, caseId)),
  ]);
  if (!caseDetail.ok) return <ApiErrorNotice error={caseDetail.error} />;
  if (!plan.ok) return <ApiErrorNotice error={plan.error} />;
  const canAdd = caseDetail.data.allowed_actions.includes("add_task");

  return (
    <div className="flex flex-1 flex-col">
      <CaseAiHeader
        workspaceId={workspaceId}
        caseId={caseId}
        caseTitle={caseDetail.data.title}
        current="plan"
      />
      <div className="flex flex-col gap-4 p-6">
        <p className="text-muted-foreground max-w-3xl text-sm">
          What the person taking over should do, and when, counted from{" "}
          {formatDateTime(plan.data.starts_at)}. Every step comes from this case and says why.{" "}
          <Explain what="continuation_plan" align="start" />
        </p>
        <div className="grid gap-4 lg:grid-cols-3">
          {plan.data.phases.map((phase) => (
            <section
              key={phase.days}
              aria-labelledby={`phase-${phase.days}`}
              className="bg-card panel-in flex flex-col overflow-hidden rounded-xl border"
            >
              <div className={cn("h-1", ACCENT[phase.days])} aria-hidden />
              <div className="border-b px-4 py-3">
                <h2 id={`phase-${phase.days}`} className="font-semibold">
                  {phase.title}
                </h2>
                <p className="text-muted-foreground text-sm">{phase.goal}</p>
              </div>
              {phase.steps.length === 0 ? (
                <p className="text-muted-foreground px-4 py-6 text-sm">Nothing for this phase.</p>
              ) : (
                <ol className="divide-y">
                  {phase.steps.map((step, i) => (
                    <li
                      key={`${step.title}-${i}`}
                      className="flex flex-col gap-1 px-4 py-3 text-sm"
                    >
                      <p className="font-medium">{step.title}</p>
                      <p className="text-muted-foreground">{step.why}</p>
                      <div className="mt-1 flex flex-wrap items-center gap-2 text-xs">
                        <Badge tone="muted">{SOURCE[step.source_kind]}</Badge>
                        <span className="text-muted-foreground">
                          by {formatDateTime(step.due_at)}
                        </span>
                        <span className="ml-auto">
                          {step.already_task ? (
                            <span className="text-muted-foreground inline-flex items-center gap-1">
                              <Check aria-hidden className="size-3.5" /> On the task list
                            </span>
                          ) : canAdd ? (
                            <ActionForm
                              action={addPlanStepAction.bind(null, workspaceId, caseId, {
                                title: step.title,
                                why: step.why,
                                due_at: step.due_at,
                              })}
                            >
                              <SubmitButton size="sm" variant="outline" pendingLabel="Adding…">
                                <Plus aria-hidden className="size-3.5" /> Add as task
                              </SubmitButton>
                            </ActionForm>
                          ) : null}
                        </span>
                      </div>
                    </li>
                  ))}
                </ol>
              )}
            </section>
          ))}
        </div>
      </div>
    </div>
  );
}
