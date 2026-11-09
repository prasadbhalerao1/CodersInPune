import Link from "next/link";

import { ActionForm, Field, inputClass, SubmitButton } from "@/components/action-form";
import { formatDateTime } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import type { KnowledgeKind, KnowledgeView } from "@/lib/types";
import { cn } from "@/lib/utils";

import { addKnowledgeAction, archiveKnowledgeAction, reviewKnowledgeAction } from "./actions";

export const KIND_LABEL: Record<KnowledgeKind, string> = {
  procedure: "Procedure",
  note: "Note",
  link: "Link",
  document: "Document",
  context: "Context",
};

export function FreshnessBadge({ item }: { item: KnowledgeView }) {
  return item.freshness === "stale" ? (
    <Badge tone="warning">Needs review</Badge>
  ) : (
    <span className="text-muted-foreground text-xs">
      Reviewed {formatDateTime(item.last_reviewed_at ?? item.created_at)}
    </span>
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
            {k.url ? (
              <a
                href={k.url}
                target="_blank"
                rel="noreferrer"
                className="font-medium hover:underline"
              >
                {k.title} ↗
              </a>
            ) : (
              <span className="font-medium">{k.title}</span>
            )}
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
            {canWrite ? (
              <ActionForm action={reviewKnowledgeAction.bind(null, workspaceId, k.id)}>
                <SubmitButton size="sm" variant="ghost" pendingLabel="…">
                  {k.freshness === "stale" ? "Mark reviewed" : "Still accurate"}
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
}: {
  workspaceId: string;
  responsibilityId: string;
  canRestrict: boolean;
}) {
  return (
    <details className="group rounded-lg border">
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
