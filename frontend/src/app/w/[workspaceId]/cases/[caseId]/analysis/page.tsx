import type { Metadata } from "next";

import { ActionForm, inputClass, SubmitButton } from "@/components/action-form";
import { ClaimBadge, ConfidenceNote, EvidenceList, RunSummary } from "@/components/ai";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { AutoRefresh } from "@/components/auto-refresh";
import { EmptyState, formatDateTime, Section } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { attempt } from "@/lib/attempt";
import { api } from "@/lib/relay-api";
import type { ClaimView, ProposalView } from "@/lib/types";
import { cn } from "@/lib/utils";

import {
  acceptProposalAction,
  analyseCaseAction,
  cancelRunAction,
  rejectProposalAction,
  reviewClaimAction,
} from "../ai-actions";
import { CaseAiHeader } from "../ai-nav";

export const metadata: Metadata = { title: "Analysis" };

const PROPOSAL_LABEL: Record<ProposalView["type"], string> = {
  knowledge_draft: "Knowledge draft",
  case_finding: "Finding to record",
  task: "Task",
  readiness_criterion: "Readiness check",
  exception: "Exception",
  handover_content: "Handover note",
  coordination_message: "Message draft",
};

type Review = { workspaceId: string; canReview: boolean };

function ClaimRow({ claim, workspaceId, canReview }: { claim: ClaimView } & Review) {
  const reviewable =
    canReview && claim.claim_type === "ai_inference" && claim.review_status === "unreviewed";
  return (
    <li className="flex flex-col gap-1.5 px-4 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <ClaimBadge kind={claim.kind} type={claim.claim_type} supported={claim.supported} />
        <ConfidenceNote value={claim.confidence} />
        {claim.audience === "managers" ? <Badge tone="warning">Managers only</Badge> : null}
        {claim.review_status !== "unreviewed" ? (
          <Badge tone="muted">
            {claim.review_status === "accepted" ? "Confirmed" : "Dismissed"}
          </Badge>
        ) : null}
        {reviewable ? (
          <span className="ml-auto flex gap-1">
            <ActionForm action={reviewClaimAction.bind(null, workspaceId, claim.id, "accepted")}>
              <SubmitButton size="sm" variant="ghost" pendingLabel="…">
                Confirm
              </SubmitButton>
            </ActionForm>
            <ActionForm action={reviewClaimAction.bind(null, workspaceId, claim.id, "rejected")}>
              <SubmitButton size="sm" variant="ghost" pendingLabel="…">
                Dismiss
              </SubmitButton>
            </ActionForm>
          </span>
        ) : null}
      </div>
      <p className={cn(claim.review_status === "rejected" && "text-muted-foreground line-through")}>
        {claim.text}
      </p>
      <EvidenceList evidence={claim.evidence} />
    </li>
  );
}

function ClaimGroup({
  title,
  description,
  claims,
  ...review
}: { title: string; description: string; claims: ClaimView[] } & Review) {
  if (claims.length === 0) return null;
  return (
    <Section title={`${title} (${claims.length})`} description={description}>
      <ul className="divide-y rounded-lg border text-sm">
        {claims.map((c) => (
          <ClaimRow key={c.id} claim={c} {...review} />
        ))}
      </ul>
    </Section>
  );
}

const STATUS_LABEL = { accepted: "Accepted", edited: "Edited & accepted", rejected: "Rejected" };

function ProposalCard({ p, workspaceId, canReview }: { p: ProposalView } & Review) {
  const pending = p.status === "pending";
  return (
    <li className="flex flex-col gap-2 px-4 py-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <Badge>{PROPOSAL_LABEL[p.type]}</Badge>
        <span className="text-muted-foreground text-xs">
          by {p.capability.replaceAll("_", " ")}
        </span>
        <ConfidenceNote value={p.confidence} />
        {p.audience === "managers" ? <Badge tone="warning">Managers only</Badge> : null}
        {p.status !== "pending" ? <Badge tone="muted">{STATUS_LABEL[p.status]}</Badge> : null}
      </div>
      <p className="font-medium">{p.title}</p>
      {p.detail ? (
        <p className="text-muted-foreground line-clamp-6 whitespace-pre-line">{p.detail}</p>
      ) : null}
      {p.reason ? <p className="text-muted-foreground text-xs">Reason: {p.reason}</p> : null}
      <EvidenceList evidence={p.evidence} />
      {pending && canReview ? (
        <div className="flex flex-col gap-2">
          <ActionForm
            action={acceptProposalAction.bind(null, workspaceId, p.id)}
            className="items-start"
          >
            <SubmitButton size="sm" pendingLabel="Applying…">
              Accept
            </SubmitButton>
          </ActionForm>
          <details>
            <summary className="text-muted-foreground hover:text-foreground cursor-pointer text-xs">
              Edit before accepting
            </summary>
            <ActionForm
              action={acceptProposalAction.bind(null, workspaceId, p.id)}
              className="mt-2 items-start"
            >
              <input type="hidden" name="edited" value="1" />
              <input
                name="title"
                defaultValue={p.title}
                aria-label="Title"
                required
                maxLength={200}
                className={inputClass}
              />
              <textarea
                name="detail"
                defaultValue={p.detail}
                aria-label="Detail"
                rows={4}
                maxLength={4000}
                className={cn(inputClass, "h-auto py-2")}
              />
              <SubmitButton size="sm" pendingLabel="Applying…">
                Save and accept
              </SubmitButton>
            </ActionForm>
          </details>
          <details>
            <summary className="text-muted-foreground hover:text-foreground cursor-pointer text-xs">
              Reject
            </summary>
            <ActionForm
              action={rejectProposalAction.bind(null, workspaceId, p.id)}
              className="mt-2 items-start"
            >
              <input
                name="reason"
                placeholder="Why? Relay won't suggest it again for the same evidence"
                aria-label="Reason"
                maxLength={1000}
                className={inputClass}
              />
              <SubmitButton size="sm" variant="outline" pendingLabel="…">
                Reject proposal
              </SubmitButton>
            </ActionForm>
          </details>
        </div>
      ) : null}
    </li>
  );
}

export default async function AnalysisPage({
  params,
}: PageProps<"/w/[workspaceId]/cases/[caseId]/analysis">) {
  const { workspaceId, caseId } = await params;
  const [caseDetail, analysis] = await Promise.all([
    attempt(api.getCase(workspaceId, caseId)),
    attempt(api.analysis(workspaceId, caseId)),
  ]);
  if (!caseDetail.ok) return <ApiErrorNotice error={caseDetail.error} />;
  if (!analysis.ok) return <ApiErrorNotice error={analysis.error} />;
  const a = analysis.data;
  const run = a.run;
  const active = run?.state === "running" || run?.state === "queued";
  const by = (...kinds: ClaimView["kind"][]) => a.claims.filter((c) => kinds.includes(c.kind));
  const timeline = by("decision", "question").sort((x, y) =>
    (x.timeline_at ?? "9").localeCompare(y.timeline_at ?? "9"),
  );
  const pending = a.proposals.filter((p) => p.status === "pending");
  const reviewed = a.proposals.filter((p) => p.status !== "pending");
  const review: Review = { workspaceId, canReview: a.can_review };

  return (
    <div className="flex flex-1 flex-col">
      <AutoRefresh active={active} />
      <CaseAiHeader
        workspaceId={workspaceId}
        caseId={caseId}
        caseTitle={caseDetail.data.title}
        current="analysis"
        actions={
          !a.can_run ? undefined : active && run ? (
            <ActionForm action={cancelRunAction.bind(null, workspaceId, run.id)}>
              <SubmitButton size="sm" variant="outline" pendingLabel="Cancelling…">
                Cancel run
              </SubmitButton>
            </ActionForm>
          ) : (
            <ActionForm action={analyseCaseAction.bind(null, workspaceId, caseId)}>
              <SubmitButton size="sm" pendingLabel="Starting…">
                {run ? "Analyse again" : "Analyse case"}
              </SubmitButton>
            </ActionForm>
          )
        }
      />
      <div className="grid gap-8 p-6 xl:grid-cols-[minmax(0,1fr)_24rem]">
        <div className="flex min-w-0 flex-col gap-8">
          {run ? (
            <div className="flex flex-col gap-3 rounded-lg border p-4">
              <RunSummary run={run} />
              {run.partial_sources.length ? (
                <p
                  role="status"
                  className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:bg-amber-950/40 dark:text-amber-200"
                >
                  {run.partial_sources.join(", ")} didn&apos;t sync cleanly, so evidence from it may
                  be missing. Treat gaps as unknown, not as absent.
                </p>
              ) : null}
              {a.hidden_restricted ? (
                <p className="text-muted-foreground text-xs">
                  Some findings rely on managers-only knowledge and aren&apos;t shown to you.
                </p>
              ) : null}
            </div>
          ) : (
            <EmptyState
              title="No analysis yet"
              description={
                a.can_run
                  ? "Analyse the case to reconstruct its state from Relay, GitHub, Linear and Notion. Every finding cites its sources; nothing changes until you accept a proposal."
                  : "A case manager hasn't analysed this case yet."
              }
            />
          )}

          <ClaimGroup
            title="Conflicts"
            description="Sources that disagree. A person needs to decide which is right."
            claims={by("conflict")}
            {...review}
          />
          <ClaimGroup
            title="Missing evidence"
            description="What a successor needs that no source covers."
            claims={by("missing")}
            {...review}
          />
          {timeline.length ? (
            <Section
              title="Decisions and open questions"
              description="In the order they happened, where the date is known."
            >
              <ol className="flex flex-col gap-4 border-l pl-5 text-sm">
                {timeline.map((c) => (
                  <li key={c.id} className="relative">
                    <span
                      aria-hidden
                      className={cn(
                        "absolute top-1.5 -left-[25px] size-2.5 rounded-full",
                        c.kind === "decision"
                          ? "bg-foreground"
                          : "border-foreground bg-background border",
                      )}
                    />
                    <p className="text-muted-foreground text-xs">
                      {c.kind === "decision" ? "Decision" : "Unresolved"} ·{" "}
                      {c.timeline_at ? formatDateTime(c.timeline_at) : "date unknown"}
                    </p>
                    <div className="mt-1 flex flex-wrap items-center gap-2">
                      <ClaimBadge kind={c.kind} type={c.claim_type} supported={c.supported} />
                      <ConfidenceNote value={c.confidence} />
                    </div>
                    <p className="mt-1">{c.text}</p>
                    <EvidenceList evidence={c.evidence} />
                  </li>
                ))}
              </ol>
            </Section>
          ) : null}
          <ClaimGroup
            title="Work in flight"
            description="Open pull requests, issues and tasks connected to this handover."
            claims={by("work")}
            {...review}
          />
          <ClaimGroup
            title="Dependencies"
            description="What else relies on this work."
            claims={by("dependency")}
            {...review}
          />
          <ClaimGroup
            title="Findings"
            description="Facts read from records, rules Relay applied, and AI inferences, each labelled."
            claims={by("finding")}
            {...review}
          />
        </div>

        <aside className="flex flex-col gap-4">
          <Section
            title={`Proposal tray${pending.length ? ` (${pending.length})` : ""}`}
            description="AI suggestions. Nothing changes until a case manager accepts one."
          >
            {pending.length === 0 ? (
              <p className="text-muted-foreground text-sm">
                {run?.ai === "on" ? "No pending proposals." : "Proposals appear when AI is on."}
              </p>
            ) : (
              <ul className="divide-y rounded-lg border">
                {pending.map((p) => (
                  <ProposalCard key={p.id} p={p} {...review} />
                ))}
              </ul>
            )}
          </Section>
          {reviewed.length ? (
            <details className="text-sm">
              <summary className="text-muted-foreground hover:text-foreground cursor-pointer">
                Reviewed ({reviewed.length})
              </summary>
              <ul className="mt-2 divide-y rounded-lg border">
                {reviewed.map((p) => (
                  <ProposalCard key={p.id} p={p} {...review} />
                ))}
              </ul>
            </details>
          ) : null}
        </aside>
      </div>
    </div>
  );
}
