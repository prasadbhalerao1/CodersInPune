import Link from "next/link";

import { ActionForm, inputClass, SubmitButton } from "@/components/action-form";
import { formatDateTime, Section } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import type { PrivacyView, ReviewItemView } from "@/lib/types";

import { configurePrivacyAction, decideReviewItemAction } from "../actions";

const DECISION = {
  pending: { label: "Waiting for review", tone: "warning" },
  confirmed: { label: "Confirmed", tone: "neutral" },
  corrected: { label: "Correction requested", tone: "warning" },
  disputed: { label: "Disputed", tone: "danger" },
} as const;

/** One item to share: what, with whom, and the outgoing owner's decision. */
export function ReviewItem({
  workspaceId,
  item: i,
  showCase = false,
}: {
  workspaceId: string;
  item: ReviewItemView;
  showCase?: boolean;
}) {
  return (
    <li className="flex flex-col gap-2 px-4 py-3 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={DECISION[i.decision].tone}>{DECISION[i.decision].label}</Badge>
        {showCase && i.case_title ? (
          <Link
            href={`/w/${workspaceId}/cases/${i.case_id}?tab=people`}
            className="text-xs font-medium underline-offset-2 hover:underline"
          >
            {i.case_title}
          </Link>
        ) : null}
      </div>
      <p>{i.summary}</p>
      <p className="text-muted-foreground text-xs">Shared with: {i.audience_label}</p>
      {i.note ? (
        <p className="text-xs">
          “{i.note}”{i.decided_by_name ? ` · ${i.decided_by_name}` : ""}
          {i.decided_at ? `, ${formatDateTime(i.decided_at)}` : ""}
        </p>
      ) : null}
      {i.can_decide && i.decision === "pending" ? (
        <div className="flex flex-wrap items-start gap-2">
          <ActionForm action={decideReviewItemAction.bind(null, workspaceId, i.id, "confirmed")}>
            <SubmitButton size="sm" variant="outline" pendingLabel="…">
              Looks right
            </SubmitButton>
          </ActionForm>
          <details>
            <summary className="text-muted-foreground hover:text-foreground cursor-pointer py-1.5 text-xs">
              Correct or dispute…
            </summary>
            <div className="mt-2 flex flex-col gap-2">
              <ActionForm
                action={decideReviewItemAction.bind(null, workspaceId, i.id, "corrected")}
              >
                <input
                  name="note"
                  required
                  maxLength={4000}
                  placeholder="What should it say instead"
                  aria-label="Correction"
                  className={inputClass}
                />
                <SubmitButton size="sm" variant="outline" pendingLabel="…">
                  Request correction
                </SubmitButton>
              </ActionForm>
              <ActionForm action={decideReviewItemAction.bind(null, workspaceId, i.id, "disputed")}>
                <input
                  name="note"
                  required
                  maxLength={4000}
                  placeholder="Why it shouldn't be shared"
                  aria-label="Dispute reason"
                  className={inputClass}
                />
                <SubmitButton size="sm" variant="ghost" pendingLabel="…">
                  Dispute
                </SubmitButton>
              </ActionForm>
            </div>
          </details>
        </div>
      ) : null}
    </li>
  );
}

export function PrivacyPanel({
  workspaceId,
  caseId,
  privacy: p,
}: {
  workspaceId: string;
  caseId: string;
  privacy: PrivacyView;
}) {
  return (
    <Section
      title="Privacy and sharing"
      description={
        p.reviewer_name
          ? `What this case shares and with whom. ${p.reviewer_name} reviews it before anyone else relies on it.`
          : "What this case shares and with whom."
      }
    >
      <p className="bg-muted/40 rounded-lg border p-3 text-sm">{p.notice}</p>
      {p.can_manage ? (
        <ActionForm
          action={configurePrivacyAction.bind(null, workspaceId, caseId)}
          className="rounded-lg border p-4 text-sm"
        >
          <p className="font-medium">Sources for this case</p>
          <p className="text-muted-foreground text-xs">
            Relay&apos;s own records are always used. Leave a connected tool unticked to keep it out
            of this case&apos;s evidence.
          </p>
          {p.sources.length ? (
            <div className="flex flex-wrap gap-4">
              {p.sources.map((s) => {
                const key = s.source.toLowerCase();
                return (
                  <label key={key} className="flex items-center gap-1.5">
                    <input type="hidden" name="connected" value={key} />
                    <input
                      type="checkbox"
                      name="source"
                      value={key}
                      defaultChecked={!p.excluded_sources.includes(key)}
                    />
                    {s.source}
                    {s.state === "partial" ? (
                      <span className="text-muted-foreground text-xs">(partial)</span>
                    ) : null}
                  </label>
                );
              })}
            </div>
          ) : (
            <p className="text-muted-foreground text-xs">No tools are connected.</p>
          )}
          {!p.notice_acknowledged_at ? (
            <label className="flex items-center gap-2">
              <input type="checkbox" name="acknowledge" required />
              I&apos;ve read the notice above and the people involved have been told.
            </label>
          ) : (
            <p className="text-muted-foreground text-xs">
              Notice confirmed {formatDateTime(p.notice_acknowledged_at)}.
            </p>
          )}
          <SubmitButton size="sm" pendingLabel="Preparing…">
            {p.items.length ? "Save and refresh the review" : "Prepare the review"}
          </SubmitButton>
        </ActionForm>
      ) : null}
      {p.items.length ? (
        <>
          <p className="text-sm" role="status">
            {p.pending ? `${p.pending} item(s) waiting for review` : "Everything has been reviewed"}
          </p>
          <ul className="divide-y rounded-lg border">
            {p.items.map((i) => (
              <ReviewItem key={i.id} workspaceId={workspaceId} item={i} />
            ))}
          </ul>
        </>
      ) : null}
    </Section>
  );
}
