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
import type { CapsuleView } from "@/lib/types";
import { cn } from "@/lib/utils";

import {
  acknowledgeCapsuleAction,
  approveCapsuleAction,
  editCapsuleAction,
} from "../../ai-actions";
import { CapsuleStatusBadge } from "../status";

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
  const [capsule, versions] = await Promise.all([
    attempt(api.capsule(workspaceId, capsuleId, version)),
    attempt(api.capsuleVersions(workspaceId, capsuleId)),
  ]);
  if (!capsule.ok) return <ApiErrorNotice error={capsule.error} />;
  const c = capsule.data;
  const base = `/w/${workspaceId}/cases/${caseId}/capsules/${capsuleId}`;

  return (
    <div className="flex flex-1 flex-col">
      <AutoRefresh active={c.generating} every={2000} />
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
      <div className="grid gap-8 p-6 xl:grid-cols-[minmax(0,1fr)_18rem]">
        <div className="flex min-w-0 flex-col gap-6">
          <div className="flex flex-col gap-2 rounded-lg border p-4 text-sm">
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
              </p>
            ) : null}
            {c.generating ? (
              <div className="mt-2 flex flex-col gap-2">
                <p role="status" className="flex items-center gap-2 text-sm">
                  <span
                    aria-hidden
                    className="border-muted-foreground/30 border-t-foreground inline-block size-3.5 animate-spin rounded-full border-2"
                  />
                  Writing an AI draft from the cited evidence. It appears here as a new version; the
                  rule-based version below stays usable meanwhile.
                </p>
                <PendingRows rows={2} label="AI draft in progress" />
              </div>
            ) : null}
            {c.summary ? <p className="mt-1 text-base">{c.summary}</p> : null}
          </div>

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

        <aside className="flex flex-col gap-3">
          <h2 className="text-sm font-semibold">Versions</h2>
          {versions.ok ? (
            <ol className="flex flex-col gap-1 text-sm">
              {versions.data.map((v) => (
                <li key={v.version}>
                  <Link
                    href={`${base}?version=${v.version}`}
                    aria-current={v.version === c.version ? "page" : undefined}
                    className={cn(
                      "block rounded-md px-2.5 py-1.5",
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
