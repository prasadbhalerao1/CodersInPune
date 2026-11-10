import type { Metadata } from "next";
import Link from "next/link";

import {
  ActionForm,
  DateTimeInput,
  Field,
  inputClass,
  SubmitButton,
} from "@/components/action-form";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { formatDateTime, PageHeader, Section } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { attempt } from "@/lib/attempt";
import { api } from "@/lib/relay-api";
import type { KnowledgeRelatedView } from "@/lib/types";
import { cn } from "@/lib/utils";

import {
  disputeKnowledgeAction,
  knowledgeFeedbackAction,
  reviewKnowledgeAction,
  updateKnowledgeAction,
} from "../actions";
import { FreshnessBadge, KIND_LABEL } from "../knowledge-list";

export const metadata: Metadata = { title: "Knowledge" };

function RelatedList({
  workspaceId,
  title,
  description,
  items,
}: {
  workspaceId: string;
  title: string;
  description: string;
  items: KnowledgeRelatedView[];
}) {
  if (!items.length) return null;
  return (
    <Section title={title} description={description}>
      <ul className="divide-y rounded-lg border text-sm">
        {items.map((r) => (
          <li key={r.id} className="flex flex-wrap items-center gap-2 px-4 py-2.5">
            <Link
              href={`/w/${workspaceId}/knowledge/${r.id}`}
              className="font-medium underline-offset-2 hover:underline"
            >
              {r.title}
            </Link>
            <span className="text-muted-foreground text-xs">
              {r.responsibility_name} · {r.state} · updated {formatDateTime(r.updated_at)}
              {r.last_reviewed_at ? ` · reviewed ${formatDateTime(r.last_reviewed_at)}` : ""}
            </span>
          </li>
        ))}
      </ul>
    </Section>
  );
}

export default async function KnowledgePage({
  params,
  searchParams,
}: PageProps<"/w/[workspaceId]/knowledge/[itemId]">) {
  const [{ workspaceId, itemId }, query] = await Promise.all([params, searchParams]);
  const [workspace, item, gov, members] = await Promise.all([
    attempt(api.getWorkspace(workspaceId)),
    attempt(api.knowledgeItem(workspaceId, itemId)),
    attempt(api.knowledgeGovernance(workspaceId, itemId)),
    attempt(api.members(workspaceId)),
  ]);
  if (!workspace.ok) return <ApiErrorNotice error={workspace.error} />;
  if (!item.ok) return <ApiErrorNotice error={item.error} />;
  if (!gov.ok) return <ApiErrorNotice error={gov.error} />;
  const k = item.data;
  const g = gov.data;
  const canWrite = !["guest", "auditor"].includes(workspace.data.role);
  const from = Number(query.from) || 0;
  const to = Number(query.to) || k.version;
  const compare =
    from && from !== to ? await attempt(api.knowledgeCompare(workspaceId, itemId, from, to)) : null;
  const base = `/w/${workspaceId}/knowledge/${itemId}`;

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader
        title={
          <span className="flex min-w-0 items-center gap-2">
            <Link href={`/w/${workspaceId}/knowledge`} className="text-muted-foreground">
              Knowledge
            </Link>
            <span className="text-muted-foreground">/</span>
            <span className="truncate">{k.title}</span>
          </span>
        }
      />
      <div className="grid gap-8 p-6 xl:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="flex min-w-0 flex-col gap-8">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <Badge tone="muted">{KIND_LABEL[k.kind]}</Badge>
            <FreshnessBadge item={k} />
            {k.visibility === "managers" ? <Badge tone="neutral">Managers only</Badge> : null}
            {k.origin !== "person" ? (
              <Badge tone="muted">{k.origin === "notion" ? "From Notion" : "AI-proposed"}</Badge>
            ) : null}
            <span className="text-muted-foreground text-xs">v{k.version}</span>
          </div>
          {k.state === "draft" && k.origin !== "person" ? (
            <p className="rounded-lg border border-amber-600/30 bg-amber-50 p-3 text-sm text-amber-950 dark:bg-amber-950/30 dark:text-amber-100">
              Imported and not yet checked by a person. Don&apos;t rely on it until the steward
              verifies it.
            </p>
          ) : null}
          {k.dispute_reason ? (
            <p className="rounded-lg border border-red-600/30 bg-red-50 p-3 text-sm text-red-950 dark:bg-red-950/30 dark:text-red-100">
              Disputed{k.disputed_by_name ? ` by ${k.disputed_by_name}` : ""}
              {k.disputed_at ? ` on ${formatDateTime(k.disputed_at)}` : ""}: {k.dispute_reason}
            </p>
          ) : null}
          {k.body ? <div className="max-w-prose text-sm whitespace-pre-line">{k.body}</div> : null}
          {k.url ? (
            <a href={k.url} target="_blank" rel="noreferrer" className="text-sm underline">
              {k.url}
            </a>
          ) : null}

          {k.kind === "adr" || k.decision_rationale ? (
            <Section
              title="Decision"
              description="Why it was decided, by whom, and whether it still holds."
            >
              <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 rounded-lg border p-4 text-sm">
                <dt className="text-muted-foreground">Rationale</dt>
                <dd className="whitespace-pre-line">{k.decision_rationale ?? "—"}</dd>
                <dt className="text-muted-foreground">Approved by</dt>
                <dd>
                  {k.decision_approver ?? "—"}
                  {k.decided_at ? ` · ${formatDateTime(k.decided_at)}` : ""}
                </dd>
                <dt className="text-muted-foreground">Still current</dt>
                <dd>
                  {k.current ? (
                    "Yes"
                  ) : g.superseded_by ? (
                    <>
                      No, superseded by{" "}
                      <Link
                        href={`/w/${workspaceId}/knowledge/${g.superseded_by.id}`}
                        className="underline"
                      >
                        {g.superseded_by.title}
                      </Link>
                    </>
                  ) : (
                    "No (expired)"
                  )}
                </dd>
              </dl>
            </Section>
          ) : null}

          <RelatedList
            workspaceId={workspaceId}
            title="Possible conflicts"
            description="Same responsibility and subject, different content. Decide which is right and supersede or dispute the other."
            items={g.conflicts}
          />
          <RelatedList
            workspaceId={workspaceId}
            title="Possible duplicates"
            description="Same title or source. Keep one and archive the rest."
            items={g.duplicates}
          />

          <Section title="Versions" description="Every edit is kept. Compare any two versions.">
            <ol className="divide-y rounded-lg border text-sm">
              {g.versions.map((v) => (
                <li key={v.version} className="flex flex-wrap items-center gap-3 px-4 py-2.5">
                  <span className="font-medium tabular-nums">v{v.version}</span>
                  <span className="min-w-0 flex-1 truncate">
                    {v.change_note ?? v.title}
                    <span className="text-muted-foreground block text-xs">
                      {v.changed_by_name} · {formatDateTime(v.changed_at)}
                    </span>
                  </span>
                  {v.version !== k.version ? (
                    <Link
                      href={`${base}?from=${v.version}&to=${k.version}`}
                      className="text-xs underline-offset-2 hover:underline"
                    >
                      Compare with current
                    </Link>
                  ) : (
                    <span className="text-muted-foreground text-xs">Current</span>
                  )}
                </li>
              ))}
            </ol>
            {compare?.ok ? (
              <pre className="bg-muted/40 overflow-x-auto rounded-lg border p-3 text-xs leading-relaxed">
                {compare.data.diff.length
                  ? compare.data.diff.map((line, i) => (
                      <span
                        key={i}
                        className={cn(
                          "block",
                          line.startsWith("+") &&
                            !line.startsWith("+++") &&
                            "text-emerald-700 dark:text-emerald-400",
                          line.startsWith("-") &&
                            !line.startsWith("---") &&
                            "text-red-700 dark:text-red-400",
                        )}
                      >
                        {line}
                      </span>
                    ))
                  : "No differences."}
              </pre>
            ) : null}
          </Section>
        </div>

        <aside className="flex flex-col gap-6">
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 rounded-lg border p-4 text-sm">
            <dt className="text-muted-foreground">Responsibility</dt>
            <dd>
              <Link
                href={`/w/${workspaceId}/responsibilities/${k.responsibility_id}`}
                className="underline-offset-2 hover:underline"
              >
                {k.responsibility_name}
              </Link>
            </dd>
            <dt className="text-muted-foreground">Author</dt>
            <dd>{k.author_name}</dd>
            <dt className="text-muted-foreground">Steward</dt>
            <dd>{k.steward_name ?? "Not assigned"}</dd>
            <dt className="text-muted-foreground">Applies to</dt>
            <dd>{k.applies_to ?? "—"}</dd>
            <dt className="text-muted-foreground">Valid</dt>
            <dd>
              {k.valid_from ? formatDateTime(k.valid_from) : "—"} →{" "}
              {k.valid_until ? formatDateTime(k.valid_until) : "open"}
            </dd>
          </dl>
          {canWrite ? (
            <div className="flex flex-wrap gap-2">
              {k.can_verify && k.review_state !== "verified" ? (
                <ActionForm action={reviewKnowledgeAction.bind(null, workspaceId, k.id)}>
                  <SubmitButton size="sm" pendingLabel="…">
                    Verify
                  </SubmitButton>
                </ActionForm>
              ) : null}
              <ActionForm
                action={knowledgeFeedbackAction.bind(null, workspaceId, k.id, "authoritative")}
              >
                <SubmitButton size="sm" variant="outline" pendingLabel="…">
                  Confirm it&apos;s right
                </SubmitButton>
              </ActionForm>
              <ActionForm action={knowledgeFeedbackAction.bind(null, workspaceId, k.id, "stale")}>
                <SubmitButton size="sm" variant="outline" pendingLabel="…">
                  Flag as stale
                </SubmitButton>
              </ActionForm>
            </div>
          ) : null}
          {g.feedback.length ? (
            <p className="text-muted-foreground text-xs">
              {g.feedback.filter((f) => f.kind === "authoritative").length} confirmed ·{" "}
              {g.feedback.filter((f) => f.kind === "stale").length} flagged stale · latest by{" "}
              {g.feedback[0].user_name}
            </p>
          ) : null}
          {canWrite && k.review_state !== "disputed" ? (
            <details>
              <summary className="text-muted-foreground hover:text-foreground cursor-pointer text-sm">
                Dispute this…
              </summary>
              <ActionForm
                action={disputeKnowledgeAction.bind(null, workspaceId, k.id)}
                className="mt-2"
              >
                <textarea
                  name="reason"
                  required
                  rows={3}
                  maxLength={4000}
                  aria-label="What is wrong"
                  className={cn(inputClass, "h-auto py-2")}
                />
                <SubmitButton size="sm" variant="outline" pendingLabel="…">
                  Dispute
                </SubmitButton>
                <p className="text-muted-foreground text-xs">
                  The content and its history stay; the steward is asked to resolve it.
                </p>
              </ActionForm>
            </details>
          ) : null}
          {k.can_edit && k.origin === "person" ? (
            <details>
              <summary className="text-muted-foreground hover:text-foreground cursor-pointer text-sm">
                Edit (creates v{k.version + 1})
              </summary>
              <ActionForm
                action={updateKnowledgeAction.bind(null, workspaceId, k.id)}
                className="mt-2"
              >
                <Field label="Title" htmlFor="kt">
                  <input
                    id="kt"
                    name="title"
                    defaultValue={k.title}
                    required
                    maxLength={200}
                    className={inputClass}
                  />
                </Field>
                <Field label="Content" htmlFor="kb">
                  <textarea
                    id="kb"
                    name="body"
                    rows={6}
                    defaultValue={k.body ?? ""}
                    maxLength={20000}
                    className={cn(inputClass, "h-auto py-2")}
                  />
                </Field>
                <Field label="What changed" htmlFor="kn">
                  <input id="kn" name="change_note" maxLength={4000} className={inputClass} />
                </Field>
                <Field label="Steward" htmlFor="ks">
                  <select
                    id="ks"
                    name="steward_user_id"
                    defaultValue={k.steward_user_id ?? ""}
                    className={inputClass}
                  >
                    <option value="">None</option>
                    {(members.ok ? members.data : [])
                      .filter((m) => m.status === "active")
                      .map((m) => (
                        <option key={m.user_id} value={m.user_id}>
                          {m.name}
                        </option>
                      ))}
                  </select>
                </Field>
                <Field label="Applies to" htmlFor="ka">
                  <input
                    id="ka"
                    name="applies_to"
                    defaultValue={k.applies_to ?? ""}
                    maxLength={500}
                    className={inputClass}
                  />
                </Field>
                <Field label="Valid until" htmlFor="kv">
                  <DateTimeInput id="kv" name="valid_until" defaultValue={k.valid_until} />
                </Field>
                <Field label="Decision rationale" htmlFor="kr">
                  <textarea
                    id="kr"
                    name="decision_rationale"
                    rows={2}
                    defaultValue={k.decision_rationale ?? ""}
                    className={cn(inputClass, "h-auto py-2")}
                  />
                </Field>
                <Field label="Approved by" htmlFor="kap">
                  <input
                    id="kap"
                    name="decision_approver"
                    defaultValue={k.decision_approver ?? ""}
                    maxLength={200}
                    className={inputClass}
                  />
                </Field>
                {g.conflicts.length || g.duplicates.length ? (
                  <Field label="Superseded by" htmlFor="ksup">
                    <select
                      id="ksup"
                      name="superseded_by_id"
                      defaultValue={k.superseded_by_id ?? ""}
                      className={inputClass}
                    >
                      <option value="">Still current</option>
                      {[...g.conflicts, ...g.duplicates].map((r) => (
                        <option key={r.id} value={r.id}>
                          {r.title}
                        </option>
                      ))}
                    </select>
                  </Field>
                ) : null}
                <SubmitButton size="sm" pendingLabel="Saving…">
                  Save new version
                </SubmitButton>
              </ActionForm>
            </details>
          ) : null}
        </aside>
      </div>
    </div>
  );
}
