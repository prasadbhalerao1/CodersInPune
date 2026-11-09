import type { Metadata } from "next";

import { ActionForm, inputClass, SubmitButton } from "@/components/action-form";
import { EvidenceList, RunSummary } from "@/components/ai";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { AutoRefresh } from "@/components/auto-refresh";
import { EmptyState, formatDateTime } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { attempt } from "@/lib/attempt";
import { api } from "@/lib/relay-api";
import type { QuestionView } from "@/lib/types";
import { cn } from "@/lib/utils";

import {
  answerQuestionAction,
  generateInterviewAction,
  questionToKnowledgeAction,
  reviewQuestionAction,
} from "../ai-actions";
import { CaseAiHeader } from "../ai-nav";

export const metadata: Metadata = { title: "Interview" };

const STATUS: Record<QuestionView["status"], string> = {
  open: "Open",
  answered: "Answered",
  unknown: "Doesn't know",
  not_applicable: "Not applicable",
  cannot_share: "Can't share",
};

function QuestionCard({
  q,
  workspaceId,
  canReview,
}: {
  q: QuestionView;
  workspaceId: string;
  canReview: boolean;
}) {
  const answerAction = answerQuestionAction.bind(null, workspaceId, q.id);
  return (
    <li className="flex flex-col gap-2 px-4 py-4 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={q.status === "open" ? "warning" : "muted"}>{STATUS[q.status]}</Badge>
        {q.ai ? (
          <Badge tone="muted" className="italic">
            AI question
          </Badge>
        ) : (
          <Badge>Rule</Badge>
        )}
        {q.reviewed_at ? <Badge tone="muted">Reviewed</Badge> : null}
        {q.asked_name ? (
          <span className="text-muted-foreground text-xs">For {q.asked_name}</span>
        ) : null}
      </div>
      <p className="font-medium">{q.question}</p>
      <p className="text-muted-foreground text-xs">Why this is asked: {q.why}</p>
      <EvidenceList evidence={q.evidence} />
      {q.answer ? (
        <blockquote className="border-l-2 pl-3 whitespace-pre-line">{q.answer}</blockquote>
      ) : null}
      {q.answered_by && q.answered_at ? (
        <p className="text-muted-foreground text-xs">
          {STATUS[q.status]} by {q.answered_by} · {formatDateTime(q.answered_at)}
        </p>
      ) : null}
      {q.can_answer ? (
        <details open={q.status === "open"}>
          <summary className="text-muted-foreground hover:text-foreground cursor-pointer text-xs">
            {q.status === "open" ? "Answer" : "Change answer"}
          </summary>
          <ActionForm action={answerAction} className="mt-2">
            <textarea
              name="answer"
              defaultValue={q.answer ?? ""}
              rows={3}
              maxLength={8000}
              aria-label="Answer"
              placeholder="Write what a successor needs to know. Never paste passwords or secrets."
              className={cn(inputClass, "h-auto py-2")}
            />
            <div className="flex flex-wrap gap-2">
              <SubmitButton size="sm" pendingLabel="Saving…">
                Save answer
              </SubmitButton>
            </div>
          </ActionForm>
          <div className="mt-2 flex flex-wrap gap-1">
            {(["unknown", "not_applicable", "cannot_share"] as const).map((status) => (
              <ActionForm key={status} action={answerAction}>
                <input type="hidden" name="status" value={status} />
                <SubmitButton size="sm" variant="ghost" pendingLabel="…">
                  {STATUS[status]}
                </SubmitButton>
              </ActionForm>
            ))}
          </div>
        </details>
      ) : null}
      {canReview && q.status !== "open" ? (
        <div className="flex flex-wrap gap-2">
          {!q.reviewed_at ? (
            <ActionForm action={reviewQuestionAction.bind(null, workspaceId, q.id)}>
              <SubmitButton size="sm" variant="outline" pendingLabel="…">
                Mark reviewed
              </SubmitButton>
            </ActionForm>
          ) : q.status === "answered" ? (
            <ActionForm action={questionToKnowledgeAction.bind(null, workspaceId, q.id)}>
              <SubmitButton size="sm" variant="outline" pendingLabel="…">
                Propose as knowledge
              </SubmitButton>
            </ActionForm>
          ) : null}
        </div>
      ) : null}
    </li>
  );
}

export default async function InterviewPage({
  params,
}: PageProps<"/w/[workspaceId]/cases/[caseId]/interview">) {
  const { workspaceId, caseId } = await params;
  const [caseDetail, interview] = await Promise.all([
    attempt(api.getCase(workspaceId, caseId)),
    attempt(api.interview(workspaceId, caseId)),
  ]);
  if (!caseDetail.ok) return <ApiErrorNotice error={caseDetail.error} />;
  if (!interview.ok) return <ApiErrorNotice error={interview.error} />;
  const i = interview.data;
  const active = i.run?.state === "running" || i.run?.state === "queued";
  const open = i.questions.filter((q) => q.status === "open").length;

  return (
    <div className="flex flex-1 flex-col">
      <AutoRefresh active={active} />
      <CaseAiHeader
        workspaceId={workspaceId}
        caseId={caseId}
        caseTitle={caseDetail.data.title}
        current="interview"
        actions={
          i.can_generate ? (
            <ActionForm action={generateInterviewAction.bind(null, workspaceId, caseId)}>
              <SubmitButton size="sm" pendingLabel="Preparing…">
                {i.questions.length ? "Ask more questions" : "Prepare questions"}
              </SubmitButton>
            </ActionForm>
          ) : undefined
        }
      />
      <div className="flex max-w-3xl flex-col gap-6 p-6">
        <p className="text-muted-foreground text-sm">
          Questions only the person handing over can answer. Answers are reviewed by a case manager
          and can be proposed as knowledge; nothing is published automatically.
        </p>
        {i.run ? (
          <div className="rounded-lg border p-4">
            <RunSummary run={i.run} />
          </div>
        ) : null}
        {i.questions.length === 0 ? (
          <EmptyState
            title="No questions yet"
            description={
              i.can_generate
                ? "Prepare questions from the case's gaps: missing knowledge, stale procedures and what the sources can't answer."
                : "A case manager hasn't prepared interview questions yet."
            }
          />
        ) : (
          <>
            <p className="text-sm" role="status">
              {open} open · {i.questions.length - open} answered or closed
            </p>
            <ul className="divide-y rounded-lg border">
              {i.questions.map((q) => (
                <QuestionCard key={q.id} q={q} workspaceId={workspaceId} canReview={i.can_review} />
              ))}
            </ul>
          </>
        )}
      </div>
    </div>
  );
}
