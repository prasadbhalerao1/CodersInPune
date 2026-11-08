import Link from "next/link";

import { ApiErrorNotice } from "@/components/api-error-notice";
import { EmptyState, formatDateTime, PageHeader } from "@/components/page";
import { Badge, CaseStatusBadge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { attempt } from "@/lib/attempt";
import { api, canManage } from "@/lib/relay-api";
import { cn } from "@/lib/utils";

import { CASE_TYPES } from "./labels";

export default async function CasesPage({
  params,
  searchParams,
}: PageProps<"/w/[workspaceId]/cases">) {
  const [{ workspaceId }, query] = await Promise.all([params, searchParams]);
  const tab = query.status === "closed" ? "closed" : "open";
  const [workspace, cases] = await Promise.all([
    attempt(api.getWorkspace(workspaceId)),
    attempt(api.listCases(workspaceId, { status: tab })),
  ]);
  if (!workspace.ok) return <ApiErrorNotice error={workspace.error} />;
  if (!cases.ok) return <ApiErrorNotice error={cases.error} />;
  const base = `/w/${workspaceId}/cases`;
  const manage = canManage(workspace.data);

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader
        title="Cases"
        actions={
          manage ? (
            <Link href={`${base}/new`} className={buttonVariants({ size: "sm" })}>
              New case
            </Link>
          ) : null
        }
      />
      <div className="flex flex-col gap-4 p-6">
        <nav aria-label="Case filters" className="flex gap-1 text-sm">
          {(["open", "closed"] as const).map((t) => (
            <Link
              key={t}
              href={t === "open" ? base : `${base}?status=closed`}
              aria-current={tab === t ? "page" : undefined}
              className={cn(
                "rounded-md px-2.5 py-1 capitalize",
                tab === t
                  ? "bg-foreground/[0.06] font-medium"
                  : "text-muted-foreground hover:bg-muted",
              )}
            >
              {t}
            </Link>
          ))}
        </nav>
        {cases.data.length === 0 ? (
          <EmptyState
            title={tab === "open" ? "No open cases" : "No closed cases yet"}
            description="Cases coordinate transfers, temporary coverage and departures, with tasks, readiness checks and approvals."
            action={
              tab === "open" && manage ? (
                <Link href={`${base}/new`} className={buttonVariants({ size: "sm" })}>
                  Start a case
                </Link>
              ) : undefined
            }
          />
        ) : (
          <ul className="divide-y rounded-lg border">
            {cases.data.map((c) => (
              <li key={c.id}>
                <Link
                  href={`${base}/${c.id}`}
                  className="hover:bg-muted/40 grid grid-cols-[1fr_auto] items-center gap-4 px-4 py-3 text-sm sm:grid-cols-[minmax(0,1fr)_9rem_8rem_7rem]"
                >
                  <span className="min-w-0">
                    <span className="block truncate font-medium">{c.title}</span>
                    <span className="text-muted-foreground block truncate text-xs">
                      {CASE_TYPES[c.case_type].label}
                      {c.affected_person_name ? ` · ${c.affected_person_name}` : ""}
                      {` · ${c.scope_count} ${c.scope_count === 1 ? "responsibility" : "responsibilities"}`}
                    </span>
                  </span>
                  <span className="hidden sm:block">
                    <CaseStatusBadge value={c.status} />
                    {c.outcome === "completed_with_exceptions" ? (
                      <span className="text-muted-foreground ml-1 text-xs">· exceptions</span>
                    ) : null}
                  </span>
                  <span className="text-muted-foreground hidden text-xs sm:block">
                    {formatDateTime(c.starts_at)}
                  </span>
                  <span className="justify-self-end">
                    {c.overdue_tasks > 0 ? (
                      <Badge tone="danger">{c.overdue_tasks} overdue</Badge>
                    ) : c.open_tasks > 0 ? (
                      <span className="text-muted-foreground text-xs tabular-nums">
                        {c.open_tasks} open tasks
                      </span>
                    ) : null}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
