import Link from "next/link";

import { inputClass } from "@/components/action-form";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { EmptyState, PageHeader, Section } from "@/components/page";
import { CriticalityBadge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { attempt } from "@/lib/attempt";
import { api, canManage } from "@/lib/relay-api";
import { cn } from "@/lib/utils";

import { AddKnowledgeForm, KnowledgeList } from "./knowledge-list";

export default async function KnowledgePage({
  params,
  searchParams,
}: PageProps<"/w/[workspaceId]/knowledge">) {
  const [{ workspaceId }, query] = await Promise.all([params, searchParams]);
  const q = typeof query.q === "string" ? query.q : undefined;
  const freshness = query.freshness === "stale" ? "stale" : undefined;
  const adding = query.add === "1";
  const target = typeof query.responsibility === "string" ? query.responsibility : undefined;
  const [overview, workspace, responsibilities] = await Promise.all([
    attempt(api.knowledge(workspaceId, { q, freshness })),
    attempt(api.getWorkspace(workspaceId)),
    adding ? attempt(api.listResponsibilities(workspaceId)) : null,
  ]);
  if (!overview.ok) return <ApiErrorNotice error={overview.error} />;
  if (!workspace.ok) return <ApiErrorNotice error={workspace.error} />;
  const o = overview.data;
  const base = `/w/${workspaceId}/knowledge`;
  const canWrite = workspace.data.role !== "guest" && workspace.data.role !== "auditor";

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader title="Knowledge" />
      <div className="grid gap-8 p-6 xl:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="flex min-w-0 flex-col gap-4">
          {adding && canWrite ? (
            <Section
              title="Add knowledge"
              description="Knowledge always belongs to a responsibility. Choose which one."
            >
              <form className="flex flex-wrap gap-2" aria-label="Choose responsibility">
                <input type="hidden" name="add" value="1" />
                <select
                  name="responsibility"
                  defaultValue={target ?? ""}
                  required
                  aria-label="Responsibility"
                  className={cn(inputClass, "max-w-sm")}
                >
                  <option value="" disabled>
                    Choose a responsibility…
                  </option>
                  {(responsibilities?.ok ? responsibilities.data : [])
                    .filter((r) => r.status === "active")
                    .map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.name}
                      </option>
                    ))}
                </select>
                <button type="submit" className={buttonVariants({ variant: "outline" })}>
                  Continue
                </button>
              </form>
              {target ? (
                <AddKnowledgeForm
                  workspaceId={workspaceId}
                  responsibilityId={target}
                  canRestrict={canManage(workspace.data)}
                  open
                />
              ) : null}
            </Section>
          ) : null}
          <form role="search" className="flex gap-2">
            <input
              name="q"
              defaultValue={q}
              placeholder="Search procedures, notes and links"
              aria-label="Search knowledge"
              className={cn(inputClass, "max-w-md")}
            />
            {freshness ? <input type="hidden" name="freshness" value={freshness} /> : null}
            <button type="submit" className={buttonVariants({ variant: "outline" })}>
              Search
            </button>
          </form>
          <nav aria-label="Freshness" className="flex gap-1 text-sm">
            {[
              {
                href: q ? `${base}?q=${encodeURIComponent(q)}` : base,
                label: "All",
                on: !freshness,
              },
              {
                href: `${base}?freshness=stale${q ? `&q=${encodeURIComponent(q)}` : ""}`,
                label: `Needs review${o.stale_items ? ` (${o.stale_items})` : ""}`,
                on: freshness === "stale",
              },
            ].map((t) => (
              <Link
                key={t.label}
                href={t.href}
                aria-current={t.on ? "page" : undefined}
                className={cn(
                  "rounded-md px-2.5 py-1",
                  t.on
                    ? "bg-foreground/[0.06] font-medium"
                    : "text-muted-foreground hover:bg-muted",
                )}
              >
                {t.label}
              </Link>
            ))}
          </nav>
          {o.results.length === 0 ? (
            <EmptyState
              title={
                q ? "Nothing matches" : freshness ? "Everything is up to date" : "No knowledge yet"
              }
              description={
                q
                  ? "Try other words; search covers titles and content."
                  : "Add procedures, links and context from a responsibility's page, or import runbooks you already keep in Notion."
              }
              action={
                !q && !freshness && workspace.data.role !== "guest" ? (
                  <Link
                    href={`/w/${workspaceId}/integrations/notion`}
                    className={buttonVariants({ variant: "outline", size: "sm" })}
                  >
                    Import from Notion
                  </Link>
                ) : undefined
              }
            />
          ) : (
            <KnowledgeList
              workspaceId={workspaceId}
              items={o.results}
              showResponsibility
              canWrite={canWrite}
            />
          )}
        </div>
        <aside className="flex flex-col gap-6">
          <Section
            title="Missing knowledge"
            description="Active responsibilities with nothing written down."
          >
            {o.missing.length === 0 ? (
              <p className="text-muted-foreground text-sm">Every responsibility has knowledge.</p>
            ) : (
              <ul className="divide-y rounded-lg border">
                {o.missing.map((m) => (
                  <li key={m.responsibility_id}>
                    <Link
                      href={`/w/${workspaceId}/responsibilities/${m.responsibility_id}#knowledge`}
                      className="hover:bg-muted/40 flex items-center justify-between gap-2 px-3 py-2 text-sm"
                    >
                      <span className="truncate">{m.responsibility_name}</span>
                      <CriticalityBadge value={m.criticality} />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Section>
          <p className="text-muted-foreground text-xs">
            {o.fresh_items} reviewed in the last 90 days · {o.stale_items} need review. Knowledge is
            written and reviewed by people; Relay never marks anything as reviewed on its own.
          </p>
        </aside>
      </div>
    </div>
  );
}
