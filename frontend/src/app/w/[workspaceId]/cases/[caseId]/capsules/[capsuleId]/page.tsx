import { History } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { ActionForm, inputClass, SubmitButton } from "@/components/action-form";
import { ClaimBadge, ConfidenceNote, EvidenceList } from "@/components/ai";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { AutoRefresh } from "@/components/auto-refresh";
import { PendingRows } from "@/components/run-progress";
import { formatDateTime, PageHeader, Section } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { attempt } from "@/lib/attempt";
import { api } from "@/lib/relay-api";
import type { CapsuleView, StrengthView } from "@/lib/types";
import { cn } from "@/lib/utils";

import {
  acknowledgeCapsuleAction,
  approveCapsuleAction,
  editCapsuleAction,
  generateCapsuleAction,
} from "../../ai-actions";
import { CapsuleStatusBadge } from "../status";
import { Copilot } from "./copilot";
import { Rehearsal } from "./rehearsal";
import { BriefCoverage } from "./coverage";
import { NextSteps } from "./next-steps";
import { VersionDiff } from "./version-diff";

export const metadata: Metadata = { title: "Handover capsule" };

const SOURCE = { rules: "Built from the analysis", ai: "AI-written draft", edit: "Edited" };

function Sections({ capsule, editable }: { capsule: CapsuleView; editable: boolean }) {
  if (capsule.sections.length === 0) {
    return <p className="text-muted-foreground text-sm">Nothing to show in this version.</p>;
  }
  return (
    <>
      {capsule.sections.map((s) => (
        <Section key={s.heading} title={s.heading}>
          <ul className="divide-y rounded-lg border text-sm">
            {s.points.map((p) => (
              <li
                key={p.key}
                className={cn("flex flex-col gap-1.5 px-4 py-3", p.redacted && "bg-muted/40")}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <ClaimBadge kind={p.kind} type={p.claim_type} />
                  <ConfidenceNote value={p.confidence} />
                  {p.redacted ? <Badge tone="warning">Redacted for the recipient</Badge> : null}
                  {p.changed ? <Badge tone="warning">Source changed since</Badge> : null}
                  {editable ? (
                    <label className="text-muted-foreground ml-auto flex items-center gap-1.5 text-xs">
                      <input
                        type="checkbox"
                        name="redacted"
                        value={p.key}
                        defaultChecked={p.redacted}
                        className="size-3.5"
                      />
                      Redact
                    </label>
                  ) : null}
                </div>
                <p className={cn(p.redacted && "text-muted-foreground")}>{p.text}</p>
                <EvidenceList evidence={p.evidence} />
              </li>
            ))}
          </ul>
        </Section>
      ))}
    </>
  );
}

export default async function CapsulePage({
  params,
  searchParams,
}: PageProps<"/w/[workspaceId]/cases/[caseId]/capsules/[capsuleId]">) {
  const [{ workspaceId, caseId, capsuleId }, query] = await Promise.all([params, searchParams]);
  const requested = typeof query.version === "string" ? Number(query.version) : undefined;
  const version = requested && Number.isInteger(requested) ? requested : undefined;
  const asMember = query.as === "member";
  const against = typeof query.compare === "string" ? Number(query.compare) : undefined;
  const compare = against && Number.isInteger(against) ? against : undefined;
  const [capsule, versions, questions, detail, rehearsal] = await Promise.all([
    attempt(api.capsule(workspaceId, capsuleId, version, asMember)),
    attempt(api.capsuleVersions(workspaceId, capsuleId)),
    attempt(api.capsuleQuestions(workspaceId, capsuleId)),
    attempt(api.getCase(workspaceId, caseId)),
    attempt(api.rehearsal(workspaceId, capsuleId)),
  ]);
  const previous = compare ? await attempt(api.capsule(workspaceId, capsuleId, compare)) : null;
  const scope = detail.ok ? detail.data.scope.filter((s) => !s.hidden) : [];
  if (!capsule.ok) return <ApiErrorNotice error={capsule.error} />;
  const c = capsule.data;
  const base = `/w/${workspaceId}/cases/${caseId}/capsules/${capsuleId}`;

  return (
    <div className="flex flex-1 flex-col">
      <AutoRefresh active={c.generating} every={c.generation === "slow" ? 10000 : 2000} />
      <PageHeader
        title={
          <span className="flex items-center gap-2">
            <Link
              href={`/w/${workspaceId}/cases/${caseId}/capsules`}
              className="text-muted-foreground hover:text-foreground truncate"
            >
              {c.case_title}
            </Link>
            <span className="text-muted-foreground">/</span>
            <span>Handover for {c.recipient_name}</span>
          </span>
        }
        actions={
          <>
            {c.can_edit ? (
              <nav aria-label="View the brief as" className="flex rounded-md border p-0.5 text-xs">
                {(
                  [
                    ["Editor", false],
                    ["Member recipient", true],
                  ] as const
                ).map(([label, member]) => (
                  <Link
                    key={label}
                    href={`?${new URLSearchParams({
                      ...(version ? { version: String(version) } : {}),
                      ...(member ? { as: "member" } : {}),
                    })}`}
                    aria-current={asMember === member ? "page" : undefined}
                    className={
                      asMember === member
                        ? "bg-foreground text-background rounded px-2 py-1"
                        : "text-muted-foreground hover:text-foreground rounded px-2 py-1"
                    }
                  >
                    View as {label.toLowerCase()}
                  </Link>
                ))}
              </nav>
            ) : null}
            {c.can_approve ? (
              <ActionForm action={approveCapsuleAction.bind(null, workspaceId, c.id)}>
                <SubmitButton
                  size="sm"
                  pendingLabel="Approving…"
                  confirm={`Approve version ${c.version} for ${c.recipient_name}?`}
                >
                  Approve
                </SubmitButton>
              </ActionForm>
            ) : null}
            {c.can_acknowledge ? (
              <ActionForm action={acknowledgeCapsuleAction.bind(null, workspaceId, c.id)}>
                <SubmitButton size="sm" pendingLabel="Saving…">
                  Acknowledge receipt
                </SubmitButton>
              </ActionForm>
            ) : null}
          </>
        }
      />
      {c.preview_as_member ? (
        <p
          role="status"
          className="border-b border-amber-600/20 bg-amber-50 px-6 py-2 text-sm text-amber-950 dark:bg-amber-950/30 dark:text-amber-100"
        >
          Previewing what a member recipient sees: managers-only points and redactions are hidden,
          and counted under &ldquo;Not included&rdquo;.
        </p>
      ) : null}
      <div className="grid gap-8 p-6 xl:grid-cols-[minmax(0,1fr)_26rem]">
        <div className="flex min-w-0 flex-col gap-6">
          <div className="bg-card flex flex-col gap-2 rounded-lg border p-4 text-sm shadow-xs">
            <p className="flex flex-wrap items-center gap-2">
              <CapsuleStatusBadge value={c.status} />
              <span className="text-muted-foreground text-xs">
                Version {c.version} · {SOURCE[c.source]} · {formatDateTime(c.created_at)}
              </span>
            </p>
            {c.approved_at ? (
              <p className="text-muted-foreground text-xs">
                Approved by {c.approved_by} · {formatDateTime(c.approved_at)}
                {c.acknowledged_at
                  ? ` · acknowledged by ${c.recipient_name} ${formatDateTime(c.acknowledged_at)}`
                  : ""}
              </p>
            ) : null}
            {c.changed_points > 0 ? (
              <p
                role="status"
                className="mt-2 rounded-md border border-amber-600/20 bg-amber-50 px-3 py-2 text-sm text-amber-950 dark:bg-amber-950/30 dark:text-amber-100"
              >
                {c.changed_points === 1
                  ? "1 statement cites a source that changed after this version was written."
                  : `${c.changed_points} statements cite sources that changed after this version was written.`}{" "}
                Re-run the analysis and review before relying on them.
                {c.changed_sources.length > 0 ? (
                  <span className="mt-1 block text-xs">
                    Changed: {c.changed_sources.join(", ")}
                  </span>
                ) : null}
              </p>
            ) : null}
            {c.generating ? (
              <div className="mt-2 flex flex-col gap-2">
                <p role="status" className="flex items-center gap-2 text-sm">
                  <span
                    aria-hidden
                    className="border-muted-foreground/30 border-t-foreground inline-block size-3.5 animate-spin rounded-full border-2"
                  />
                  {c.generation === "slow"
                    ? "The AI draft is taking longer than expected (the model or the background worker may be busy). The rule-based version below is complete and usable."
                    : "Writing an AI draft from the cited evidence. It appears here as a new version; the rule-based version below stays usable meanwhile."}
                </p>
                <PendingRows rows={2} label="AI draft in progress" />
              </div>
            ) : null}
            {c.generation === "stalled" || c.generation === "failed" ? (
              <div
                role="status"
                className="mt-2 flex flex-wrap items-center gap-3 rounded-md border border-amber-600/20 bg-amber-50 px-3 py-2 text-sm text-amber-950 dark:bg-amber-950/30 dark:text-amber-100"
              >
                <span className="min-w-0 flex-1">
                  {c.generation === "stalled"
                    ? "The AI draft did not finish in time and was abandoned."
                    : "The AI draft could not be written (AI switched off, over budget or the provider failed)."}{" "}
                  This rule-based version is complete and cites its evidence.
                </span>
                {c.can_edit ? (
                  <ActionForm action={generateCapsuleAction.bind(null, workspaceId, caseId)}>
                    <input type="hidden" name="recipient_user_id" value={c.recipient_user_id} />
                    <SubmitButton size="sm" variant="outline" pendingLabel="Retrying…">
                      Try the AI draft again
                    </SubmitButton>
                  </ActionForm>
                ) : null}
              </div>
            ) : null}
            {c.summary ? <p className="mt-1 text-base">{c.summary}</p> : null}
            {c.strength ? <Strength s={c.strength} /> : null}
          </div>

          <BriefCoverage
            capsule={c}
            interviewHref={`/w/${workspaceId}/cases/${caseId}/interview`}
          />
          {c.acknowledged_at && detail.ok ? (
            <NextSteps workspaceId={workspaceId} capsule={c} detail={detail.data} />
          ) : null}
          {previous?.ok ? (
            <VersionDiff
              from={previous.data}
              to={c}
              closeHref={version ? `${base}?version=${version}` : base}
            />
          ) : null}

          {c.can_edit ? (
            <ActionForm action={editCapsuleAction.bind(null, workspaceId, c.id)} className="gap-6">
              <textarea
                name="summary"
                defaultValue={c.summary ?? ""}
                rows={2}
                maxLength={2000}
                aria-label="Summary"
                placeholder="Optional summary for the recipient"
                className={cn(inputClass, "h-auto py-2")}
              />
              <Sections capsule={c} editable />
              <div>
                <SubmitButton size="sm" variant="outline" pendingLabel="Saving…">
                  Save as new version
                </SubmitButton>
                <p className="text-muted-foreground mt-1 text-xs">
                  Saving creates a new version, which needs approving again.
                </p>
              </div>
            </ActionForm>
          ) : (
            <Sections capsule={c} editable={false} />
          )}

          {scope.length > 0 ? (
            <Section
              title="Where this work came from"
              description="The history behind each responsibility in this handover: decisions, incidents and changes, with their sources."
            >
              <ul className="bg-card divide-y rounded-lg border text-sm shadow-xs">
                {scope.map((s) => (
                  <li key={s.id} className="flex items-center gap-3 px-4 py-2.5">
                    <History aria-hidden className="text-muted-foreground size-4" />
                    <span className="min-w-0 flex-1 truncate font-medium">
                      {s.responsibility_name}
                    </span>
                    <Link
                      href={`/w/${workspaceId}/responsibilities/${s.responsibility_id}/timeline`}
                      className="text-primary text-xs font-medium hover:underline"
                    >
                      Open memory replay
                    </Link>
                  </li>
                ))}
              </ul>
            </Section>
          ) : null}

          {c.contacts.length ? (
            <Section
              title="Who to ask"
              description="From ownership records: current holders, backups and recent previous owners of this work."
            >
              <ul className="divide-y rounded-lg border text-sm">
                {c.contacts.map((p) => (
                  <li key={p.name} className="px-4 py-2.5">
                    <span className="font-medium">{p.name}</span>
                    <span className="text-muted-foreground block text-xs">{p.why}</span>
                  </li>
                ))}
              </ul>
            </Section>
          ) : null}

          <Section
            title="Omissions"
            description="What this handover deliberately leaves out, so gaps are visible rather than silent."
          >
            {c.omissions.length === 0 ? (
              <p className="text-muted-foreground text-sm">Nothing was left out.</p>
            ) : (
              <ul className="divide-y rounded-lg border text-sm">
                {c.omissions.map((o) => (
                  <li key={o.reason} className="flex items-center justify-between px-4 py-2.5">
                    <span>{o.reason}</span>
                    <span className="text-muted-foreground tabular-nums">{o.count}</span>
                  </li>
                ))}
              </ul>
            )}
          </Section>
        </div>

        <aside className="flex flex-col gap-6 xl:sticky xl:top-20 xl:self-start">
          {rehearsal?.ok ? (
            <Rehearsal workspaceId={workspaceId} capsuleId={c.id} drills={rehearsal.data.drills} />
          ) : null}
          {questions.ok ? (
            <Copilot
              workspaceId={workspaceId}
              caseId={caseId}
              capsuleId={c.id}
              initial={questions.data}
              suggestions={followUps(c)}
            />
          ) : (
            <ApiErrorNotice error={questions.error} />
          )}
          <h2 className="-mb-3 text-sm font-semibold" data-tour="capsule-versions">
            Versions
          </h2>
          {versions.ok ? (
            <ol className="flex flex-col gap-1 text-sm">
              {versions.data.map((v) => (
                <li key={v.version} className="group flex items-center gap-1">
                  <Link
                    href={`${base}?version=${v.version}`}
                    aria-current={v.version === c.version ? "page" : undefined}
                    className={cn(
                      "block flex-1 rounded-md px-2.5 py-1.5",
                      v.version === c.version ? "bg-foreground/[0.06]" : "hover:bg-muted",
                    )}
                  >
                    <span className="font-medium">v{v.version}</span>{" "}
                    <span className="text-muted-foreground text-xs">
                      {SOURCE[v.source]}
                      {v.approved_at ? " · approved" : ""}
                      {v.acknowledged ? " · acknowledged" : ""}
                    </span>
                  </Link>
                  {v.version !== c.version ? (
                    <Link
                      href={`${base}?${version ? `version=${version}&` : ""}compare=${v.version}`}
                      className="text-primary shrink-0 px-1 text-xs font-medium hover:underline"
                      aria-label={`Compare v${v.version} with v${c.version}`}
                    >
                      Compare
                    </Link>
                  ) : null}
                </li>
              ))}
            </ol>
          ) : (
            <ApiErrorNotice error={versions.error} />
          )}
        </aside>
      </div>
    </div>
  );
}

const STRENGTH = {
  strong: ["Strong evidence", "border-emerald-600/30 text-emerald-800 dark:text-emerald-300"],
  partial: ["Partial evidence", "border-amber-600/30 text-amber-900 dark:text-amber-200"],
  weak: ["Weak evidence", "border-red-600/30 text-red-800 dark:text-red-300"],
} as const;

// How far the brief can be relied on, from its sources and coverage (computed by the API).
function Strength({ s }: { s: StrengthView }) {
  const [label, tone] = STRENGTH[s.level];
  return (
    <p className="mt-2 flex flex-wrap items-center gap-2 text-xs">
      <span className={`rounded-full border px-2 py-0.5 font-medium ${tone}`}>{label}</span>
      <span className="text-muted-foreground">
        {s.cited}/{s.points} statements cited · {s.fresh} on recent, unchanged sources · {s.covered}
        /{s.scope} responsibilities covered
        {s.conflicts ? ` · ${s.conflicts} conflicting` : ""}
      </span>
    </p>
  );
}

// Rule-based follow-ups: uncovered responsibilities first, then open questions in the brief.
function followUps(c: CapsuleView): string[] {
  const uncovered = c.coverage
    .filter((x) => x.cited === 0)
    .map((x) => `What should I know about ${x.name}?`);
  const open = c.sections
    .flatMap((s) => s.points)
    .filter((p) => p.kind === "missing" || p.kind === "question")
    .map((p) => {
      const text = p.text.length > 110 ? `${p.text.slice(0, 107).trimEnd()}…` : p.text;
      // Gaps are written as statements; ask about them as questions.
      return text.trimEnd().endsWith("?") ? text : `What do we know about this gap: ${text}`;
    });
  return [...uncovered, ...open, "What should I do first this week?"];
}
