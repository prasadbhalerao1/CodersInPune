import type { Metadata } from "next";
import Link from "next/link";

import { ActionForm, inputClass, SubmitButton } from "@/components/action-form";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { EmptyState, formatDateTime, Section } from "@/components/page";
import { attempt } from "@/lib/attempt";
import { api } from "@/lib/relay-api";
import { cn } from "@/lib/utils";

import { generateCapsuleAction } from "../ai-actions";
import { CaseAiHeader } from "../ai-nav";
import { CapsuleStatusBadge } from "./status";

export const metadata: Metadata = { title: "Handover capsules" };

export default async function CapsulesPage({
  params,
}: PageProps<"/w/[workspaceId]/cases/[caseId]/capsules">) {
  const { workspaceId, caseId } = await params;
  const [caseDetail, capsules, analysis] = await Promise.all([
    attempt(api.getCase(workspaceId, caseId)),
    attempt(api.caseCapsules(workspaceId, caseId)),
    attempt(api.analysis(workspaceId, caseId)),
  ]);
  if (!caseDetail.ok) return <ApiErrorNotice error={caseDetail.error} />;
  if (!capsules.ok) return <ApiErrorNotice error={capsules.error} />;
  const canGenerate = analysis.ok && analysis.data.can_run;
  const members = canGenerate ? await attempt(api.members(workspaceId)) : null;
  const recipients = members?.ok ? members.data.filter((m) => m.status === "active") : [];
  const analysed = analysis.ok && analysis.data.run !== null;

  return (
    <div className="flex flex-1 flex-col">
      <CaseAiHeader
        workspaceId={workspaceId}
        caseId={caseId}
        caseTitle={caseDetail.data.title}
        current="capsules"
      />
      <div className="flex max-w-3xl flex-col gap-8 p-6">
        {canGenerate ? (
          <Section
            title="Generate a handover capsule"
            description="A handover for one person, limited to what they're allowed to see. You review and approve it before they acknowledge it."
          >
            {!analysed ? (
              <p className="text-sm">
                <Link
                  href={`/w/${workspaceId}/cases/${caseId}/analysis`}
                  className="font-medium underline-offset-2 hover:underline"
                >
                  Analyse the case first →
                </Link>
              </p>
            ) : (
              <ActionForm
                action={generateCapsuleAction.bind(null, workspaceId, caseId)}
                className="flex-row flex-wrap items-center"
              >
                <select
                  name="recipient_user_id"
                  required
                  defaultValue=""
                  aria-label="Recipient"
                  className={cn(inputClass, "max-w-xs")}
                >
                  <option value="" disabled>
                    Choose the recipient…
                  </option>
                  {recipients.map((m) => (
                    <option key={m.user_id} value={m.user_id}>
                      {m.name}
                      {m.role === "owner" || m.role === "admin" ? " (manager)" : ""}
                    </option>
                  ))}
                </select>
                <SubmitButton size="sm" pendingLabel="Generating…">
                  Generate capsule
                </SubmitButton>
              </ActionForm>
            )}
          </Section>
        ) : null}
        <Section title="Capsules">
          {capsules.data.length === 0 ? (
            <EmptyState
              title="No capsules yet"
              description={
                canGenerate
                  ? "Generate one for the person taking over."
                  : "When a handover is prepared for you, it appears here."
              }
            />
          ) : (
            <ul className="divide-y rounded-lg border">
              {capsules.data.map((c) => (
                <li key={c.id}>
                  <Link
                    href={`/w/${workspaceId}/cases/${caseId}/capsules/${c.id}`}
                    className="hover:bg-muted/40 flex flex-wrap items-center gap-3 px-4 py-3 text-sm"
                  >
                    <span className="min-w-0 flex-1 font-medium">For {c.recipient_name}</span>
                    <CapsuleStatusBadge value={c.status} />
                    <span className="text-muted-foreground text-xs tabular-nums">
                      v{c.version} · {formatDateTime(c.updated_at)}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Section>
      </div>
    </div>
  );
}
