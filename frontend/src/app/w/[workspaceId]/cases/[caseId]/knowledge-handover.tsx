import { ActionForm, inputClass, SubmitButton } from "@/components/action-form";
import { formatDateTime, Section } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { recordHandoverAction } from "@/app/w/[workspaceId]/knowledge/actions";
import { FreshnessBadge, KIND_LABEL } from "@/app/w/[workspaceId]/knowledge/knowledge-list";
import type { CaseKnowledgeItemView } from "@/lib/types";
import { cn } from "@/lib/utils";

/** For each responsibility in the case: its knowledge, what was handed over, what's missing. */
export function KnowledgeHandover({
  workspaceId,
  caseId,
  entries,
  canRecord,
}: {
  workspaceId: string;
  caseId: string;
  entries: CaseKnowledgeItemView[];
  canRecord: boolean;
}) {
  if (entries.length === 0) return null;
  const handed = (e: CaseKnowledgeItemView) =>
    new Set(e.records.filter((r) => r.outcome === "handed_over").map((r) => r.knowledge_item_id));
  return (
    <Section
      title="Knowledge handover"
      description="What the recipient needs to know, what was handed over, and what is still missing."
    >
      <div className="flex flex-col gap-3">
        {entries.map((e) => {
          const done = handed(e);
          const missing = e.records.filter((r) => r.outcome === "missing");
          return (
            <div key={e.responsibility_id} className="rounded-lg border">
              <p className="flex items-center gap-2 border-b px-4 py-2 text-sm font-medium">
                {e.responsibility_name}
                <span className="text-muted-foreground text-xs font-normal">
                  {done.size}/{e.knowledge.length} handed over
                </span>
              </p>
              {e.knowledge.length === 0 ? (
                <p className="text-muted-foreground px-4 py-3 text-sm">
                  No knowledge recorded for this responsibility. Note what&apos;s missing below and
                  capture it before the handover completes.
                </p>
              ) : (
                <ul className="divide-y">
                  {e.knowledge.map((k) => (
                    <li key={k.id} className="flex flex-wrap items-center gap-2 px-4 py-2 text-sm">
                      <Badge tone="muted">{KIND_LABEL[k.kind]}</Badge>
                      {k.url ? (
                        <a
                          href={k.url}
                          target="_blank"
                          rel="noreferrer"
                          className="hover:underline"
                        >
                          {k.title} ↗
                        </a>
                      ) : (
                        <span>{k.title}</span>
                      )}
                      <span className="flex-1" />
                      <FreshnessBadge item={k} />
                      {done.has(k.id) ? (
                        <Badge tone="neutral">Handed over</Badge>
                      ) : canRecord ? (
                        <ActionForm
                          action={recordHandoverAction.bind(
                            null,
                            workspaceId,
                            caseId,
                            e.responsibility_id,
                            "handed_over",
                            k.id,
                          )}
                        >
                          <SubmitButton size="sm" variant="outline" pendingLabel="…">
                            Mark handed over
                          </SubmitButton>
                        </ActionForm>
                      ) : null}
                    </li>
                  ))}
                </ul>
              )}
              {missing.length ? (
                <ul className="border-t bg-amber-50/50 px-4 py-2 text-sm dark:bg-amber-950/10">
                  {missing.map((m) => (
                    <li key={m.id} className="text-amber-900 dark:text-amber-200">
                      Missing: {m.note}
                      <span className="text-muted-foreground ml-2 text-xs">
                        {m.recorded_by_name} · {formatDateTime(m.recorded_at)}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : null}
              {canRecord ? (
                <ActionForm
                  action={recordHandoverAction.bind(
                    null,
                    workspaceId,
                    caseId,
                    e.responsibility_id,
                    "missing",
                    null,
                  )}
                  className="flex-row items-center gap-2 border-t px-4 py-2"
                >
                  <input
                    name="note"
                    maxLength={4000}
                    placeholder="Something the recipient needs that isn't written down…"
                    aria-label={`Missing knowledge for ${e.responsibility_name}`}
                    className={cn(inputClass, "h-8")}
                  />
                  <SubmitButton size="sm" variant="ghost">
                    Note missing
                  </SubmitButton>
                </ActionForm>
              ) : null}
            </div>
          );
        })}
      </div>
    </Section>
  );
}
