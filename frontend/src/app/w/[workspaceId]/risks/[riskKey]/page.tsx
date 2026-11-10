import Link from "next/link";

import { ActionForm, Field, inputClass, SubmitButton } from "@/components/action-form";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { formatDateTime, PageHeader, Section } from "@/components/page";
import { CriticalityBadge, RiskStatusBadge, SeverityBadge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { attempt } from "@/lib/attempt";
import { api, canManage } from "@/lib/relay-api";

import { decideRiskAction } from "../actions";

export default async function RiskPage({ params }: PageProps<"/w/[workspaceId]/risks/[riskKey]">) {
  const { workspaceId, riskKey } = await params;
  const [workspace, risks] = await Promise.all([
    attempt(api.getWorkspace(workspaceId)),
    attempt(api.risks(workspaceId, "all")),
  ]);
  if (!workspace.ok) return <ApiErrorNotice error={workspace.error} />;
  if (!risks.ok) return <ApiErrorNotice error={risks.error} />;
  const key = decodeURIComponent(riskKey);
  const risk = risks.data.find((r) => r.key === key);
  const base = `/w/${workspaceId}`;

  if (!risk) {
    return (
      <div className="flex flex-1 flex-col">
        <PageHeader title="Risk resolved" />
        <div className="flex flex-col items-start gap-3 p-6 text-sm">
          <p>This risk is no longer detected. The gap that caused it has been fixed.</p>
          <Link
            href={`${base}/risks?status=resolved`}
            className={buttonVariants({ variant: "outline", size: "sm" })}
          >
            See resolved risks
          </Link>
        </div>
      </div>
    );
  }

  const manage = canManage(workspace.data);
  const subjects = risk.responsibility ? [risk.responsibility] : risk.related;
  const assetLink = risk.asset_id ? `/w/${workspaceId}/assets/${risk.asset_id}` : null;
  const decide = (action: "acknowledge" | "accept" | "reopen" | "remediate" | "dismiss") =>
    decideRiskAction.bind(null, workspaceId, risk.key, action);

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader
        title={risk.title}
        actions={
          <>
            <RiskStatusBadge value={risk.status} />
            <SeverityBadge value={risk.severity} />
          </>
        }
      />
      <div className="grid gap-8 p-6 xl:grid-cols-[minmax(0,42rem)_22rem]">
        <div className="flex flex-col gap-6">
          {assetLink ? (
            <p className="text-sm">
              Asset:{" "}
              <a href={assetLink} className="font-medium underline-offset-2 hover:underline">
                {risk.asset_name}
              </a>
            </p>
          ) : null}
          <Section title="Why this is a risk">
            <p className="text-sm">{risk.explanation}</p>
          </Section>
          <Section title="Recommended action">
            <p className="text-sm">{risk.recommendation}</p>
          </Section>
          <Section
            title={subjects.length > 1 ? "Affected responsibilities" : "Affected responsibility"}
          >
            <ul className="divide-y rounded-lg border">
              {subjects.map((s) => (
                <li key={s.id}>
                  <Link
                    href={`${base}/responsibilities/${s.id}`}
                    className="hover:bg-muted/40 flex items-center justify-between gap-3 px-4 py-3 text-sm"
                  >
                    <span className="font-medium">{s.name}</span>
                    <CriticalityBadge value={s.criticality} />
                  </Link>
                </li>
              ))}
            </ul>
          </Section>
          <p className="text-muted-foreground text-xs">
            Rule: {risk.rule}
            {risk.first_detected_at
              ? ` · first detected ${formatDateTime(risk.first_detected_at)}`
              : ""}
          </p>
        </div>

        <aside className="flex flex-col gap-6">
          <Section title="Status">
            <div className="rounded-lg border p-4 text-sm">
              <p className="flex items-center gap-2">
                <RiskStatusBadge value={risk.status} />
                {risk.status === "accepted" && risk.accepted_until
                  ? `until ${formatDateTime(risk.accepted_until)}`
                  : null}
              </p>
              {risk.decided_by_name && risk.decided_at ? (
                <p className="text-muted-foreground mt-2 text-xs">
                  {risk.decided_by_name} · {formatDateTime(risk.decided_at)}
                </p>
              ) : (
                <p className="text-muted-foreground mt-2 text-xs">No decision recorded yet.</p>
              )}
              {risk.note ? <p className="mt-2 whitespace-pre-line">“{risk.note}”</p> : null}
            </div>
          </Section>

          {manage ? (
            <>
              {risk.status === "open" ? (
                <Section
                  title="Acknowledge"
                  description="You've seen it and someone is on it. It stays in open work."
                >
                  <ActionForm action={decide("acknowledge")}>
                    <input
                      name="note"
                      maxLength={4000}
                      placeholder="Who is handling it (optional)"
                      aria-label="Note"
                      className={inputClass}
                    />
                    <div>
                      <SubmitButton size="sm" variant="outline">
                        Acknowledge
                      </SubmitButton>
                    </div>
                  </ActionForm>
                </Section>
              ) : null}
              {risk.status !== "in_remediation" ? (
                <Section
                  title="Start remediation"
                  description="Someone is fixing the underlying condition. Relay resolves the risk by itself once it's gone."
                >
                  <ActionForm action={decide("remediate")}>
                    <input
                      name="note"
                      maxLength={4000}
                      placeholder="What is being done (optional)"
                      aria-label="Remediation note"
                      className={inputClass}
                    />
                    <div>
                      <SubmitButton size="sm" variant="outline">
                        Mark in remediation
                      </SubmitButton>
                    </div>
                  </ActionForm>
                </Section>
              ) : null}
              {risk.status !== "dismissed" ? (
                <Section
                  title="Dismiss"
                  description="Not a real risk here. The reason is kept; it reopens if it's resolved and comes back."
                >
                  <ActionForm action={decide("dismiss")}>
                    <input
                      name="note"
                      required
                      maxLength={4000}
                      placeholder="Why this doesn't apply"
                      aria-label="Dismissal reason"
                      className={inputClass}
                    />
                    <div>
                      <SubmitButton size="sm" variant="ghost">
                        Dismiss
                      </SubmitButton>
                    </div>
                  </ActionForm>
                </Section>
              ) : null}
              {risk.status !== "accepted" ? (
                <Section
                  title="Accept for a period"
                  description="Tolerate it deliberately. It reopens automatically on the date."
                >
                  <ActionForm action={decide("accept")}>
                    <Field label="Reason" htmlFor="accept-note">
                      <textarea
                        id="accept-note"
                        name="note"
                        required
                        rows={3}
                        maxLength={4000}
                        className={`${inputClass} h-auto py-2`}
                      />
                    </Field>
                    <Field label="Accepted until" htmlFor="accept-until">
                      <input
                        id="accept-until"
                        type="date"
                        name="accepted_until"
                        required
                        className={inputClass}
                      />
                    </Field>
                    <div>
                      <SubmitButton size="sm" variant="outline">
                        Accept risk
                      </SubmitButton>
                    </div>
                  </ActionForm>
                </Section>
              ) : null}
              {risk.status !== "open" ? (
                <ActionForm action={decide("reopen")}>
                  <SubmitButton size="sm" variant="ghost">
                    Reopen
                  </SubmitButton>
                </ActionForm>
              ) : null}
            </>
          ) : null}
        </aside>
      </div>
    </div>
  );
}
