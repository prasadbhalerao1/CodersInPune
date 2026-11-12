import {
  ArrowLeftRight,
  ArrowRight,
  BookOpen,
  Briefcase,
  CalendarClock,
  CheckCircle2,
  FlaskConical,
  ShieldAlert,
  ShieldOff,
  UserMinus,
  UserRoundX,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";

import { ApiErrorNotice } from "@/components/api-error-notice";
import { RelayLines } from "@/components/brand";
import { HandoverBanner } from "@/components/handover-banner";
import { GettingStarted } from "@/components/guidance";
import { EmptyState, PageHeader, Section } from "@/components/page";
import { CaseStatusBadge, ROLE_LABEL, SeverityBadge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import {
  Avatar,
  IconTile,
  RelativeTime,
  Ring,
  SegmentBar,
  type TileTone,
} from "@/components/visual";
import { attempt } from "@/lib/attempt";
import { api, canManage } from "@/lib/relay-api";
import type { CaseSummary } from "@/lib/types";
import { cn } from "@/lib/utils";

type Line = { label: string; count: number; href: string; icon: LucideIcon; tone: TileTone };
type Metric = {
  label: string;
  value: number;
  href: string;
  icon: LucideIcon;
  tone: TileTone;
  hint: string;
};

export default async function OverviewPage({ params }: PageProps<"/w/[workspaceId]">) {
  const { workspaceId } = await params;
  const [workspace, overview, openCases, accepted, mine, guidance] = await Promise.all([
    attempt(api.getWorkspace(workspaceId)),
    attempt(api.overview(workspaceId)),
    attempt(api.listCases(workspaceId, { status: "open" })),
    attempt(api.risks(workspaceId, "accepted")),
    attempt(api.myWork(workspaceId)),
    attempt(api.guidance(workspaceId)),
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
  const now = soon.getTime();
  soon.setDate(soon.getDate() + 14);
  const expiring = accepted.ok
    ? accepted.data.filter((r) => r.accepted_until && new Date(r.accepted_until) <= soon)
    : [];
  const ops = insights?.ok ? insights.data.operations : null;
  const know = insights?.ok ? insights.data.knowledge : null;
  // Everything here is a count of real records with a link to them; zero rows are hidden.
  const attention: Line[] = [
    {
      label: "High-severity continuity risks",
      count: o.risks_by_severity.high,
      href: `${base}/risks`,
      icon: ShieldAlert,
      tone: "danger",
    },
    {
      label: "Responsibilities without a primary owner",
      count: o.without_primary_owner,
      href: `${base}/risks`,
      icon: UserRoundX,
      tone: "danger",
    },
    {
      label: "Critical responsibilities without a backup",
      count: o.critical_without_backup,
      href: `${base}/risks`,
      icon: ShieldOff,
      tone: "warning",
    },
    {
      label: "Overdue continuity tasks and cases",
      count: ops ? ops.overdue_tasks + ops.overdue_cases : 0,
      href: `${base}/cases`,
      icon: CalendarClock,
      tone: "warning",
    },
    {
      label: "Accepted risks expiring within 14 days",
      count: expiring.length,
      href: `${base}/risks?status=accepted`,
      icon: CalendarClock,
      tone: "neutral",
    },
    {
      label: "Responsibilities with no knowledge",
      count: know ? know.responsibilities_missing_knowledge : 0,
      href: `${base}/knowledge`,
      icon: BookOpen,
      tone: "warning",
    },
    {
      label: "Knowledge items due for review",
      count: know ? know.stale_items : 0,
      href: `${base}/knowledge?freshness=stale`,
      icon: BookOpen,
      tone: "neutral",
    },
  ].filter((a): a is Line => a.count > 0);

  // Coverage: active responsibilities with a primary owner, and a backup when critical.
  const gaps = Math.min(
    o.active_responsibilities,
    o.without_primary_owner + o.critical_without_backup,
  );
  const covered = o.active_responsibilities - gaps;
  const coverage = o.active_responsibilities
    ? Math.round((covered / o.active_responsibilities) * 100)
    : 100;
  const coverageTone = coverage >= 85 ? "success" : coverage >= 60 ? "warning" : "danger";
  const canSimulate = ["owner", "admin", "continuity_manager"].includes(workspace.data.role);
  const metrics: Metric[] = [
    {
      label: "Active responsibilities",
      value: o.active_responsibilities,
      href: `${base}/responsibilities`,
      icon: Briefcase,
      tone: "primary",
      hint: `${covered} fully covered`,
    },
    {
      label: "Without a primary owner",
      value: o.without_primary_owner,
      href: `${base}/risks`,
      icon: UserMinus,
      tone: o.without_primary_owner > 0 ? "danger" : "success",
      hint: o.without_primary_owner > 0 ? "Nobody is accountable" : "Every one has an owner",
    },
    {
      label: "Critical without backup",
      value: o.critical_without_backup,
      href: `${base}/risks`,
      icon: ShieldOff,
      tone: o.critical_without_backup > 0 ? "warning" : "success",
      hint:
        o.critical_without_backup > 0
          ? "One absence away from a gap"
          : "All critical work has cover",
    },
    {
      label: "Open continuity risks",
      value: o.open_risks,
      href: `${base}/risks`,
      icon: ShieldAlert,
      tone: o.risks_by_severity.high > 0 ? "danger" : "neutral",
      hint:
        o.acknowledged_risks || o.accepted_risks
          ? `${o.acknowledged_risks} acknowledged · ${o.accepted_risks} accepted`
          : `${o.risks_by_severity.high} high severity`,
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
      <div className="mx-auto flex w-full max-w-350 flex-col gap-6 p-6">
        {mine.ok ? (
          <HandoverBanner workspaceId={workspaceId} handovers={mine.data.handovers} />
        ) : null}
        {guidance.ok ? <GettingStarted workspaceId={workspaceId} guidance={guidance.data} /> : null}
        {emergencies.length > 0 ? (
          <section
            aria-label="Emergency cases"
            className="rounded-lg border border-red-600/25 bg-red-50/60 dark:bg-red-950/20"
          >
            <p className="flex items-center gap-2 px-4 pt-3 text-xs font-semibold text-red-900 dark:text-red-200">
              <span aria-hidden className="motion-ping size-2 rounded-full bg-red-600" />
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

        {o.active_responsibilities > 0 ? (
          <section
            aria-label="Continuity health"
            className="bg-card relative overflow-hidden rounded-xl border shadow-xs"
          >
            <RelayLines className="absolute inset-y-0 right-0 hidden h-full w-[34%] opacity-70 lg:block" />
            <div className="relative grid gap-6 p-6 lg:grid-cols-[auto_minmax(0,1fr)_minmax(0,18rem)] lg:items-center">
              <Ring value={coverage} tone={coverageTone} size={128} stroke={11}>
                <span className="tabular text-3xl leading-none font-semibold">{coverage}%</span>
                <span className="text-muted-foreground mt-1 text-[11px]">covered</span>
              </Ring>
              <div className="flex min-w-0 flex-col gap-4">
                <div>
                  <p className="text-muted-foreground text-xs font-medium tracking-wide uppercase">
                    Continuity health
                  </p>
                  <p className="font-display mt-1 text-2xl leading-snug text-balance">
                    {covered} of {o.active_responsibilities} responsibilities have the owner and
                    cover they need.
                    {gaps > 0 ? (
                      <span className="text-muted-foreground">
                        {" "}
                        {gaps === 1 ? "One gap" : `${gaps} gaps`} would hurt if someone left
                        tomorrow.
                      </span>
                    ) : null}
                  </p>
                </div>
                <SegmentBar
                  label="Open risks by severity"
                  segments={[
                    { label: "high", value: o.risks_by_severity.high, className: "bg-red-600" },
                    {
                      label: "medium",
                      value: o.risks_by_severity.medium,
                      className: "bg-amber-500",
                    },
                    { label: "low", value: o.risks_by_severity.low, className: "bg-slate-400" },
                  ]}
                />
              </div>
              <div className="flex flex-col gap-3 lg:border-l lg:pl-6">
                {insights?.ok ? (
                  <Link href={`${base}/insights`} className="group flex flex-col gap-1">
                    <span className="text-muted-foreground text-xs font-medium">
                      Continuity debt
                    </span>
                    <span className="tabular text-2xl font-semibold">
                      {insights.data.continuity_debt}
                      <span className="text-muted-foreground ml-1 text-xs font-normal">points</span>
                    </span>
                    <span className="text-muted-foreground group-hover:text-foreground text-xs">
                      Fixing an item lowers it by its points →
                    </span>
                  </Link>
                ) : null}
                {canSimulate ? (
                  <Link
                    href={`${base}/simulator`}
                    className="bg-background/80 hover:border-primary/40 lift flex items-center gap-3 rounded-lg border p-3 text-sm"
                  >
                    <IconTile icon={FlaskConical} />
                    <span className="min-w-0 flex-1">
                      <span className="block font-medium">Test your readiness</span>
                      <span className="text-muted-foreground block text-xs">
                        What if someone were away tomorrow?
                      </span>
                    </span>
                    <ArrowRight aria-hidden className="text-muted-foreground size-4" />
                  </Link>
                ) : null}
              </div>
            </div>
          </section>
        ) : null}

        <div className="motion-stagger grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {metrics.map((m) => (
            <Link
              key={m.label}
              href={m.href}
              className="bg-card lift flex items-start gap-3 rounded-lg border p-4 shadow-xs"
            >
              <IconTile icon={m.icon} tone={m.tone} />
              <span className="min-w-0">
                <span className="text-muted-foreground block text-xs font-medium">{m.label}</span>
                <span
                  className={cn(
                    "tabular mt-0.5 block text-2xl leading-tight font-semibold",
                    m.tone === "danger" && m.value > 0 && "text-red-700 dark:text-red-400",
                  )}
                >
                  {m.value}
                </span>
                <span className="text-muted-foreground block truncate text-xs">{m.hint}</span>
              </span>
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
          <>
            <div className="grid gap-6 lg:grid-cols-2">
              <Section title="Needs attention" description="Each line opens the records behind it.">
                {attention.length === 0 ? (
                  <p className="bg-card text-muted-foreground flex items-center gap-2 rounded-lg border px-4 py-3 text-sm">
                    <CheckCircle2 aria-hidden className="size-4 text-emerald-600" />
                    Nothing needs attention right now.
                  </p>
                ) : (
                  <ul className="motion-stagger bg-card divide-y overflow-hidden rounded-lg border shadow-xs">
                    {attention.map((a) => (
                      <li key={a.label}>
                        <Link
                          href={a.href}
                          className="group hover:bg-muted/50 flex items-center gap-3 px-4 py-2.5 text-sm transition-colors"
                        >
                          <IconTile icon={a.icon} tone={a.tone} className="size-7" />
                          <span className="min-w-0 flex-1">{a.label}</span>
                          <span className="tabular text-base font-semibold">{a.count}</span>
                          <ArrowRight
                            aria-hidden
                            className="text-muted-foreground size-4 transition-transform group-hover:translate-x-0.5"
                          />
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </Section>

              <Section
                title="Handovers in motion"
                description="Continuity cases that are open now."
                aside={
                  <Link
                    href={`${base}/cases`}
                    className="text-muted-foreground text-xs hover:underline"
                  >
                    All cases
                  </Link>
                }
              >
                {active.length === 0 ? (
                  <p className="bg-card text-muted-foreground rounded-lg border px-4 py-3 text-sm">
                    No open cases. Start one when someone leaves, joins or goes on leave.
                  </p>
                ) : (
                  <ul className="motion-stagger flex flex-col gap-2">
                    {active.slice(0, 5).map((c) => (
                      <li key={c.id}>
                        <CaseCard href={`${base}/cases/${c.id}`} c={c} />
                      </li>
                    ))}
                  </ul>
                )}
              </Section>
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
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
                  <p className="bg-card text-muted-foreground rounded-lg border p-4 text-sm">
                    No open risks. Coverage looks healthy.
                  </p>
                ) : (
                  <ul className="motion-stagger bg-card divide-y overflow-hidden rounded-lg border shadow-xs">
                    {o.top_risks.map((risk) => (
                      <li key={risk.key}>
                        <Link
                          href={`${base}/risks/${encodeURIComponent(risk.key)}`}
                          className={cn(
                            "hover:bg-muted/50 flex items-start gap-3 border-l-2 px-4 py-3 transition-colors",
                            risk.severity === "high"
                              ? "border-l-red-600"
                              : risk.severity === "medium"
                                ? "border-l-amber-500"
                                : "border-l-transparent",
                          )}
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

              <Section title="Recent ownership changes" description="Who took on what, and when.">
                {o.recent_changes.length === 0 ? (
                  <p className="bg-card text-muted-foreground rounded-lg border p-4 text-sm">
                    No ownership changes yet.
                  </p>
                ) : (
                  <ol className="motion-stagger bg-card flex flex-col rounded-lg border p-4 shadow-xs">
                    {o.recent_changes.map((c, i) => (
                      <li key={i} className="relative flex gap-3 pb-4 last:pb-0">
                        {i < o.recent_changes.length - 1 ? (
                          <span
                            aria-hidden
                            className="bg-border absolute top-9 bottom-0 left-4 w-px"
                          />
                        ) : null}
                        <Avatar name={c.assignee_name} />
                        <div className="min-w-0 flex-1 text-sm">
                          <p>
                            <span className="font-medium">{c.assignee_name}</span>{" "}
                            <span className="text-muted-foreground">
                              {c.change_type === "assigned" ? "became" : "stopped being"}{" "}
                              {ROLE_LABEL[c.role].toLowerCase()} for
                            </span>{" "}
                            <Link
                              href={`${base}/responsibilities/${c.responsibility_id}`}
                              className="font-medium hover:underline"
                            >
                              {c.responsibility_name}
                            </Link>
                          </p>
                          <p className="text-muted-foreground text-xs">
                            <RelativeTime iso={c.changed_at} now={now} />
                            {c.reason ? ` · ${c.reason}` : ""}
                          </p>
                        </div>
                      </li>
                    ))}
                  </ol>
                )}
              </Section>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

const CASE_LABEL: Record<CaseSummary["case_type"], string> = {
  transfer: "Transfer",
  coverage: "Coverage",
  departure: "Departure",
  onboarding: "Onboarding",
  project_handover: "Project handover",
};

function CaseCard({ href, c }: { href: string; c: CaseSummary }) {
  return (
    <Link
      href={href}
      className="bg-card lift flex items-center gap-3 rounded-lg border px-4 py-3 shadow-xs"
    >
      {c.affected_person_name ? (
        <Avatar name={c.affected_person_name} />
      ) : (
        <IconTile icon={ArrowLeftRight} tone="neutral" />
      )}
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-medium">{c.title}</span>
        <span className="text-muted-foreground block truncate text-xs">
          {CASE_LABEL[c.case_type]} · {c.scope_count}{" "}
          {c.scope_count === 1 ? "responsibility" : "responsibilities"} · {c.open_tasks} open{" "}
          {c.open_tasks === 1 ? "task" : "tasks"}
          {c.overdue_tasks ? (
            <span className="text-red-700 dark:text-red-400"> · {c.overdue_tasks} overdue</span>
          ) : null}
        </span>
      </span>
      <CaseStatusBadge value={c.status} />
    </Link>
  );
}
