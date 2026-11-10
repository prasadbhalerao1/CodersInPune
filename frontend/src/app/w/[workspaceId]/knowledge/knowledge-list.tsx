import Link from "next/link";

import { ActionForm, Field, inputClass, SubmitButton } from "@/components/action-form";
import { formatDateTime } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import type { KnowledgeKind, KnowledgeState, KnowledgeView } from "@/lib/types";
import { cn } from "@/lib/utils";

import { addKnowledgeAction, archiveKnowledgeAction, reviewKnowledgeAction } from "./actions";

export const KIND_LABEL: Record<KnowledgeKind, string> = {
  procedure: "Procedure",
  note: "Note",
  link: "Link",
  document: "Document",
  context: "Context",
  adr: "Decision (ADR)",
  faq: "FAQ",
  postmortem: "Postmortem",
  escalation_contact: "Escalation contact",
  onboarding_resource: "Onboarding resource",
  project_overview: "Project overview",
};

const STATE: Record<
  KnowledgeState,
  { label: string; tone: "muted" | "warning" | "danger" | "neutral" }
> = {
  draft: { label: "Draft · unverified", tone: "warning" },
  verified: { label: "Verified", tone: "neutral" },
  disputed: { label: "Disputed", tone: "danger" },
  stale: { label: "Needs review", tone: "warning" },
  expired: { label: "Expired", tone: "muted" },
  inaccessible: { label: "Source unavailable", tone: "danger" },
  archived: { label: "Archived", tone: "muted" },
};

export function FreshnessBadge({ item }: { item: KnowledgeView }) {
  return item.state === "verified" ? (
    <span className="text-muted-foreground text-xs">
      Verified · reviewed {formatDateTime(item.last_reviewed_at ?? item.created_at)}
    </span>
  ) : (
    <Badge tone={STATE[item.state].tone}>{STATE[item.state].label}</Badge>
  );
}

/** Notion-style readable list: title, provenance, freshness, then the content itself. */
export function KnowledgeList({
  workspaceId,
  items,
  showResponsibility = false,
  canWrite,
}: {
  workspaceId: string;
  items: KnowledgeView[];
  showResponsibility?: boolean;
  canWrite: boolean;
}) {
  return (
    <ul className="divide-y rounded-lg border">
      {items.map((k) => (
        <li key={k.id} className="flex flex-col gap-1.5 px-4 py-3">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <Badge tone="muted">{KIND_LABEL[k.kind]}</Badge>
            <Link
              href={`/w/${workspaceId}/knowledge/${k.id}`}
              className="font-medium underline-offset-2 hover:underline"
            >
              {k.title}
            </Link>
            {k.url ? (
              <a href={k.url} target="_blank" rel="noreferrer" className="text-xs hover:underline">
                source ↗
              </a>
            ) : null}
            {k.version > 1 ? (
              <span className="text-muted-foreground text-xs">v{k.version}</span>
            ) : null}
            {!k.current && k.kind === "adr" ? <Badge tone="muted">Superseded</Badge> : null}
            {k.origin === "notion" ? <Badge tone="muted">From Notion</Badge> : null}
            {k.visibility === "managers" ? <Badge tone="neutral">Managers only</Badge> : null}
            <span className="flex-1" />
            <FreshnessBadge item={k} />
          </div>
          {k.body ? (
            <p className="text-foreground/85 line-clamp-6 max-w-prose text-sm whitespace-pre-line">
              {k.body}
            </p>
          ) : null}
          <div className="text-muted-foreground flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
            <span>
              {k.origin === "notion" ? "Synced from Notion, mapped by " : "By "}
              {k.author_name} · {formatDateTime(k.created_at)}
              {k.last_reviewed_by_name ? ` · last reviewed by ${k.last_reviewed_by_name}` : ""}
            </span>
            {showResponsibility ? (
              <Link
                href={`/w/${workspaceId}/responsibilities/${k.responsibility_id}`}
                className="hover:text-foreground hover:underline"
              >
                {k.responsibility_name}
              </Link>
            ) : null}
            <span className="flex-1" />
            {k.dispute_reason ? (
              <span className="text-red-700 dark:text-red-300">
                Disputed{k.disputed_by_name ? ` by ${k.disputed_by_name}` : ""}: {k.dispute_reason}
              </span>
            ) : null}
            {canWrite && (k.review_state === "verified" || k.can_verify) ? (
              <ActionForm action={reviewKnowledgeAction.bind(null, workspaceId, k.id)}>
                <SubmitButton size="sm" variant="ghost" pendingLabel="…">
                  {k.review_state !== "verified"
                    ? "Verify"
                    : k.freshness === "stale"
                      ? "Mark reviewed"
                      : "Still accurate"}
                </SubmitButton>
              </ActionForm>
            ) : null}
            {k.can_edit && k.origin === "person" ? (
              <ActionForm action={archiveKnowledgeAction.bind(null, workspaceId, k.id)}>
                <SubmitButton size="sm" variant="ghost" pendingLabel="…">
                  Archive
                </SubmitButton>
              </ActionForm>
            ) : null}
          </div>
        </li>
      ))}
    </ul>
  );
}

export function AddKnowledgeForm({
  workspaceId,
  responsibilityId,
  canRestrict,
  open = false,
}: {
  workspaceId: string;
  responsibilityId: string;
  canRestrict: boolean;
  open?: boolean;
}) {
  return (
    <details className="group rounded-lg border" open={open}>
      <summary className="text-muted-foreground hover:text-foreground cursor-pointer list-none px-4 py-2.5 text-sm select-none">
        + Add knowledge
      </summary>
      <ActionForm
        action={addKnowledgeAction.bind(null, workspaceId, responsibilityId)}
        className="border-t p-4"
      >
        <div className="grid gap-3 sm:grid-cols-[10rem_1fr]">
          <Field label="Type" htmlFor="k-kind">
            <select id="k-kind" name="kind" defaultValue="procedure" className={inputClass}>
              {Object.entries(KIND_LABEL).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Title" htmlFor="k-title">
            <input id="k-title" name="title" required maxLength={200} className={inputClass} />
          </Field>
        </div>
        <Field label="Link (optional)" htmlFor="k-url">
          <input
            id="k-url"
            name="url"
            type="url"
            pattern="https?://.+"
            placeholder="https://"
            className={inputClass}
          />
        </Field>
        <Field label="Content" htmlFor="k-body">
          <textarea
            id="k-body"
            name="body"
            rows={5}
            maxLength={20000}
            placeholder="Steps, context, gotchas. Write it so someone new could act on it."
            className={cn(inputClass, "h-auto py-2")}
          />
        </Field>
        <div className="flex items-center gap-3">
          <SubmitButton size="sm">Save</SubmitButton>
          {canRestrict ? (
            <label className="text-muted-foreground flex items-center gap-2 text-xs">
              <input type="checkbox" name="visibility" value="managers" className="size-3.5" />
              Managers only
            </label>
          ) : null}
        </div>
      </ActionForm>
    </details>
  );
}
