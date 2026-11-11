import Link from "next/link";

import { ApiErrorNotice } from "@/components/api-error-notice";
import { HandoverBanner } from "@/components/handover-banner";
import { EmptyState, formatDateTime, PageHeader, Section } from "@/components/page";
import { CaseStatusBadge, ROLE_LABEL, SeverityBadge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { attempt } from "@/lib/attempt";
import { api, canManage } from "@/lib/relay-api";

export default async function OverviewPage({ params }: PageProps<"/w/[workspaceId]">) {
  const { workspaceId } = await params;
  const [workspace, overview, openCases, accepted, mine] = await Promise.all([
    attempt(api.getWorkspace(workspaceId)),
    attempt(api.overview(workspaceId)),
    attempt(api.listCases(workspaceId, { status: "open" })),
    attempt(api.risks(workspaceId, "accepted")),
    attempt(api.myWork(workspaceId)),
  ]);
  const seesInsights = workspace.ok && ["owner", "admin", "auditor"].includes(workspace.data.role);
  const insights = seesInsights ? await attempt(api.insights(workspaceId)) : null;
  if (!workspace.ok) return <ApiErrorNotice error={workspace.error} />;
  if (!overview.ok) return <ApiErrorNotice error={overview.error} />;
  const o = overview.data;
  const emergencies = openCases.ok ? openCases.data.filter((c) => c.emergency) : [];
  const active = openCases.ok ? openCases.data.filter((c) => !c.emergency) : [];
  const base = `/w/${workspaceId}`;
  const soon = new Date();
  soon.setDate(soon.getDate() + 14);
  const expiring = accepted.ok
    ? accepted.data.filter((r) => r.accepted_until && new Date(r.accepted_until) <= soon)
    : [];
  const ops = insights?.ok ? insights.data.operations : null;
  const know = insights?.ok ? insights.data.knowledge : null;
  // Everything here is a count of real records with a link to them; zero rows are hidden.
  const attention = [
    {
      label: "High-severity continuity risks",
      count: o.risks_by_severity.high,
      href: `${base}/risks`,
    },
    {
      label: "Responsibilities without a primary owner",
      count: o.without_primary_owner,
      href: `${base}/risks`,
    },
    {
      label: "Critical responsibilities without a backup",
      count: o.critical_without_backup,
      href: `${base}/risks`,
    },
    {
      label: "Overdue continuity tasks and cases",
      count: ops ? ops.overdue_tasks + ops.overdue_cases : 0,
      href: `${base}/cases`,
    },
    {
      label: "Accepted risks expiring within 14 days",
      count: expiring.length,
      href: `${base}/risks?status=accepted`,
    },
    {
      label: "Responsibilities with no knowledge",
      count: know ? know.responsibilities_missing_knowledge : 0,
      href: `${base}/knowledge`,
    },
    {
      label: "Knowledge items due for review",
      count: know ? know.stale_items : 0,
      href: `${base}/knowledge?freshness=stale`,
    },
  ].filter((a) => a.count > 0);
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
      note:
        o.acknowledged_risks || o.accepted_risks
          ? `${o.acknowledged_risks} acknowledged · ${o.accepted_risks} accepted`
          : undefined,
    },
  ];

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader
        title={workspace.data.name}
        description="Where continuity stands today: what needs attention, what is moving, and what changed."
        actions={
          canManage(workspace.data) ? (
            <Link href={`${base}/responsibilities/new`} className={buttonVariants({ size: "sm" })}>
              New responsibility
            </Link>
          ) : null
        }
      />
      <div className="flex flex-col gap-8 p-6">
        {mine.ok ? (
          <HandoverBanner workspaceId={workspaceId} handovers={mine.data.handovers} />
        ) : null}
        {emergencies.length > 0 ? (
          <section
            aria-label="Emergency cases"
            className="rounded-lg border border-red-600/25 bg-red-50/60 dark:bg-red-950/20"
          >
            <p className="px-4 pt-3 text-xs font-semibold text-red-900 dark:text-red-200">
              {emergencies.length === 1
                ? "Emergency case"
                : `${emergencies.length} emergency cases`}
            </p>
            <ul className="divide-y divide-red-600/10">
              {emergencies.map((c) => (
                <li key={c.id}>
                  <Link
                    href={`${base}/cases/${c.id}`}
                    className="flex items-center gap-3 px-4 py-2.5 text-sm hover:bg-red-100/50 dark:hover:bg-red-950/30"
                  >
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium">{c.title}</span>
                      <span className="text-muted-foreground block truncate text-xs">
                        {c.emergency_reason}
                      </span>
                    </span>
                    <CaseStatusBadge value={c.status} />
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        ) : null}
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
              {"note" in m && m.note ? (
                <p className="text-muted-foreground mt-0.5 text-xs">{m.note}</p>
              ) : null}
            </Link>
          ))}
        </div>

        {o.active_responsibilities > 0 ? (
          <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_22rem]">
            <Section
              title="Attention required"
              description="Each line links to the records behind it."
            >
              {attention.length === 0 ? (
                <p className="text-muted-foreground rounded-lg border px-4 py-3 text-sm">
                  Nothing needs attention right now.
                </p>
              ) : (
                <ul className="divide-y rounded-lg border">
                  {attention.map((a) => (
                    <li key={a.label}>
                      <Link
                        href={a.href}
                        className="hover:bg-muted/40 flex items-center gap-3 px-4 py-2.5 text-sm"
                      >
                        <span className="w-8 text-right font-semibold tabular-nums">{a.count}</span>
                        <span className="min-w-0 flex-1">{a.label}</span>
                        <span aria-hidden className="text-muted-foreground">
                          →
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </Section>
            {insights?.ok ? (
              <Section title="Continuity Debt" description="Largest contributors right now.">
                <Link
                  href={`${base}/insights`}
                  className="hover:border-foreground/20 flex flex-col gap-2 rounded-lg border p-4"
                >
                  <span className="text-3xl font-semibold tabular-nums">
                    {insights.data.continuity_debt}
                  </span>
                  <ul className="flex flex-col gap-1 text-xs">
                    {[...insights.data.debt]
                      .filter((d) => d.points > 0)
                      .sort((x, y) => y.points - x.points)
                      .slice(0, 3)
                      .map((d) => (
                        <li key={d.key} className="flex gap-2">
                          <span className="text-muted-foreground min-w-0 flex-1 truncate">
                            {d.label}
                          </span>
                          <span className="tabular-nums">{d.points}</span>
                        </li>
                      ))}
                  </ul>
                  <span className="text-muted-foreground text-xs">
                    Fixing an item lowers the debt by its points →
                  </span>
                </Link>
              </Section>
            ) : null}
          </div>
        ) : null}

        {active.length > 0 ? (
          <Section title="Active continuity cases">
            <ul className="divide-y rounded-lg border">
              {active.slice(0, 6).map((c) => (
                <li key={c.id}>
                  <Link
                    href={`${base}/cases/${c.id}`}
                    className="hover:bg-muted/40 flex items-center gap-3 px-4 py-2.5 text-sm"
                  >
                    <span className="min-w-0 flex-1 truncate font-medium">{c.title}</span>
                    <span className="text-muted-foreground text-xs capitalize">{c.case_type}</span>
                    <CaseStatusBadge value={c.status} />
                  </Link>
                </li>
              ))}
            </ul>
            {active.length > 6 ? (
              <Link
                href={`${base}/cases`}
                className="text-muted-foreground text-xs hover:underline"
              >
                All {active.length} active cases →
              </Link>
            ) : null}
          </Section>
        ) : null}

        {o.active_responsibilities === 0 ? (
          <EmptyState
            title="Start your responsibility catalogue"
            description="Add the people who keep things running, then record the responsibilities they own."
            action={
              <div className="flex gap-2">
                <Link
                  href={`${base}/import`}
                  className={buttonVariants({ variant: "ghost", size: "sm" })}
                >
                  Import CSV
                </Link>
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
