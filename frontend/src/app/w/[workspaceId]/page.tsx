import Link from "next/link";

import { ApiErrorNotice } from "@/components/api-error-notice";
import { EmptyState, formatDateTime, PageHeader, Section } from "@/components/page";
import { ROLE_LABEL, SeverityBadge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { attempt } from "@/lib/attempt";
import { api, canManage } from "@/lib/relay-api";

export default async function OverviewPage({ params }: PageProps<"/w/[workspaceId]">) {
  const { workspaceId } = await params;
  const [workspace, overview] = await Promise.all([
    attempt(api.getWorkspace(workspaceId)),
    attempt(api.overview(workspaceId)),
  ]);
  if (!workspace.ok) return <ApiErrorNotice error={workspace.error} />;
  if (!overview.ok) return <ApiErrorNotice error={overview.error} />;
  const o = overview.data;
  const base = `/w/${workspaceId}`;
  const metrics = [
    {
      label: "Active responsibilities",
      value: o.active_responsibilities,
      href: `${base}/responsibilities`,
    },
    {
      label: "Without a primary owner",
      value: o.without_primary_owner,
      href: `${base}/risks`,
      alert: o.without_primary_owner > 0,
    },
    {
      label: "Critical without backup",
      value: o.critical_without_backup,
      href: `${base}/risks`,
      alert: o.critical_without_backup > 0,
    },
    {
      label: "Open continuity risks",
      value: o.open_risks,
      href: `${base}/risks`,
      alert: o.risks_by_severity.high > 0,
    },
  ];

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader
        title={workspace.data.name}
        actions={
          canManage(workspace.data) ? (
            <Link href={`${base}/responsibilities/new`} className={buttonVariants({ size: "sm" })}>
              New responsibility
            </Link>
          ) : null
        }
      />
      <div className="flex flex-col gap-8 p-6">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {metrics.map((m) => (
            <Link
              key={m.label}
              href={m.href}
              className="hover:border-foreground/20 rounded-lg border p-4 transition-colors"
            >
              <p className="text-muted-foreground text-xs">{m.label}</p>
              <p
                className={`mt-1 text-2xl font-semibold tabular-nums ${m.alert ? "text-red-700 dark:text-red-400" : ""}`}
              >
                {m.value}
              </p>
            </Link>
          ))}
        </div>

        {o.active_responsibilities === 0 ? (
          <EmptyState
            title="Start your responsibility catalogue"
            description="Add the people who keep things running, then record the responsibilities they own."
            action={
              <div className="flex gap-2">
                <Link
                  href={`${base}/people`}
                  className={buttonVariants({ variant: "outline", size: "sm" })}
                >
                  Add people
                </Link>
                <Link
                  href={`${base}/responsibilities/new`}
                  className={buttonVariants({ size: "sm" })}
                >
                  Add a responsibility
                </Link>
              </div>
            }
          />
        ) : (
          <div className="grid gap-8 lg:grid-cols-2">
            <Section
              title="Top risks"
              description="Deterministic checks on the current catalogue."
              aside={
                <Link
                  href={`${base}/risks`}
                  className="text-muted-foreground text-xs hover:underline"
                >
                  All risks
                </Link>
              }
            >
              {o.top_risks.length === 0 ? (
                <p className="text-muted-foreground rounded-lg border p-4 text-sm">
                  No open risks. Coverage looks healthy.
                </p>
              ) : (
                <ul className="divide-y rounded-lg border">
                  {o.top_risks.map((risk) => (
                    <li key={risk.key}>
                      <Link
                        href={`${base}/risks/${encodeURIComponent(risk.key)}`}
                        className="hover:bg-muted/60 flex items-start gap-3 px-4 py-3"
                      >
                        <SeverityBadge value={risk.severity} />
                        <span className="min-w-0 text-sm">
                          <span className="font-medium">{risk.title}</span>
                          <span className="text-muted-foreground block truncate">
                            {risk.responsibility?.name ?? risk.person_name}
                          </span>
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </Section>
            <Section title="Recent ownership changes">
              {o.recent_changes.length === 0 ? (
                <p className="text-muted-foreground rounded-lg border p-4 text-sm">
                  No ownership changes yet.
                </p>
              ) : (
                <ul className="divide-y rounded-lg border">
                  {o.recent_changes.map((c, i) => (
                    <li key={i} className="px-4 py-3 text-sm">
                      <Link
                        href={`${base}/responsibilities/${c.responsibility_id}`}
                        className="font-medium hover:underline"
                      >
                        {c.responsibility_name}
                      </Link>
                      <p className="text-muted-foreground">
                        {c.assignee_name}{" "}
                        {c.change_type === "assigned" ? "assigned as" : "ended as"}{" "}
                        {ROLE_LABEL[c.role].toLowerCase()} · {formatDateTime(c.changed_at)}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </Section>
          </div>
        )}
      </div>
    </div>
  );
}
