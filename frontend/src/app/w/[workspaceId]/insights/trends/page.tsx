import type { Metadata } from "next";
import Link from "next/link";

import { ActionForm, SubmitButton } from "@/components/action-form";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { formatDateTime, PageHeader, Section } from "@/components/page";
import { attempt } from "@/lib/attempt";
import { api, canManage } from "@/lib/relay-api";
import type { MetricView } from "@/lib/types";
import { cn } from "@/lib/utils";

import { takeSnapshotAction } from "./actions";

export const metadata: Metadata = { title: "Trends" };

const PERIODS = [30, 90, 180] as const;

function format(m: MetricView): string {
  if (m.value === null) return "No data";
  return m.unit === "share"
    ? `${Math.round(m.value * 100)}%`
    : `${m.value} ${m.unit.replace("median ", "")}`;
}

function MetricCard({ m }: { m: MetricView }) {
  const buckets = Object.entries(m.distribution).filter(
    ([k]) => k.includes("_days") && !k.startsWith("median") && !k.startsWith("p90"),
  );
  const max = Math.max(1, ...buckets.map(([, v]) => v));
  return (
    <div className="flex flex-col gap-2 rounded-lg border p-4">
      <p className="text-muted-foreground text-xs">{m.name}</p>
      <p
        className={cn(
          "text-2xl font-semibold tabular-nums",
          m.value === null && "text-muted-foreground text-lg",
        )}
      >
        {format(m)}
      </p>
      <p className="text-muted-foreground text-xs tabular-nums">
        {m.unit === "share" ? `${m.numerator} of ${m.denominator}` : `${m.sample_size} completed`} ·
        sample {m.sample_size}
        {m.distribution.p90_days !== undefined ? ` · p90 ${m.distribution.p90_days} days` : ""}
      </p>
      {buckets.length && m.sample_size ? (
        <div className="flex flex-col gap-1" aria-label="Distribution">
          {buckets.map(([k, v]) => (
            <div key={k} className="flex items-center gap-2 text-xs">
              <span className="text-muted-foreground w-24">{k.replaceAll("_", " ")}</span>
              <span className="bg-muted h-1.5 flex-1 rounded-full">
                <span
                  className="bg-foreground block h-1.5 rounded-full"
                  style={{ width: `${(v / max) * 100}%` }}
                />
              </span>
              <span className="w-6 text-right tabular-nums">{v}</span>
            </div>
          ))}
        </div>
      ) : null}
      <details className="text-xs">
        <summary className="text-muted-foreground hover:text-foreground cursor-pointer">
          How this is counted
        </summary>
        <dl className="mt-2 flex flex-col gap-1.5">
          <dt className="font-medium">Definition</dt>
          <dd className="text-muted-foreground">{m.definition}</dd>
          <dt className="font-medium">Coverage</dt>
          <dd className="text-muted-foreground">{m.coverage}</dd>
          <dt className="font-medium">Limitations</dt>
          <dd className="text-muted-foreground">{m.limitations}</dd>
        </dl>
      </details>
    </div>
  );
}

export default async function TrendsPage({
  params,
  searchParams,
}: PageProps<"/w/[workspaceId]/insights/trends">) {
  const [{ workspaceId }, query] = await Promise.all([params, searchParams]);
  const days = PERIODS.find((d) => String(d) === query.days) ?? 90;
  const [workspace, metrics, snapshots] = await Promise.all([
    attempt(api.getWorkspace(workspaceId)),
    attempt(api.trendMetrics(workspaceId, days)),
    attempt(api.metricSnapshots(workspaceId)),
  ]);
  if (!workspace.ok) return <ApiErrorNotice error={workspace.error} />;
  if (!metrics.ok) return <ApiErrorNotice error={metrics.error} />;
  const base = `/w/${workspaceId}/insights`;

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader
        title="Trends"
        actions={
          <Link href={base} className="text-sm underline-offset-2 hover:underline">
            Current state →
          </Link>
        }
      />
      <div className="flex max-w-6xl flex-col gap-8 p-6">
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <span className="text-muted-foreground">Period</span>
          {PERIODS.map((d) => (
            <Link
              key={d}
              href={`${base}/trends?days=${d}`}
              aria-current={d === days ? "page" : undefined}
              className={cn(
                "rounded-md px-2.5 py-1",
                d === days
                  ? "bg-foreground/[0.06] font-medium"
                  : "text-muted-foreground hover:bg-muted",
              )}
            >
              Last {d} days
            </Link>
          ))}
          <span className="text-muted-foreground text-xs">
            {formatDateTime(metrics.data.period_start)} → {formatDateTime(metrics.data.period_end)}
          </span>
          <span className="flex-1" />
          {canManage(workspace.data) ? (
            <ActionForm action={takeSnapshotAction.bind(null, workspaceId, days)}>
              <SubmitButton size="sm" variant="outline" pendingLabel="Saving…">
                Save a snapshot
              </SubmitButton>
            </ActionForm>
          ) : null}
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {metrics.data.metrics.map((m) => (
            <MetricCard key={m.key} m={m} />
          ))}
        </div>
        <p className="text-muted-foreground text-xs">
          Metrics describe the organisation&apos;s handovers and tools, never individuals. Periods
          without data show &ldquo;No data&rdquo; rather than zero, and nothing before Relay
          recorded it is estimated.
        </p>
        <Section
          title="Saved snapshots"
          description="Each computed the same way over its own period, so they compare like with like."
        >
          {snapshots.ok && snapshots.data.length ? (
            <div className="overflow-x-auto rounded-lg border">
              <table className="w-full text-sm">
                <thead className="bg-muted/40 text-muted-foreground text-left text-xs">
                  <tr>
                    <th className="px-3 py-2 font-medium">Taken</th>
                    {snapshots.data[0].metrics.map((m) => (
                      <th key={m.key} className="px-3 py-2 font-medium">
                        {m.name}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {snapshots.data.map((s) => (
                    <tr key={s.id}>
                      <td className="px-3 py-2 text-xs whitespace-nowrap">
                        {formatDateTime(s.taken_at)}
                      </td>
                      {s.metrics.map((m) => (
                        <td key={m.key} className="px-3 py-2 tabular-nums">
                          {format(m)}
                          <span className="text-muted-foreground block text-xs">
                            n={m.sample_size}
                          </span>
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-muted-foreground text-sm">No snapshots yet.</p>
          )}
        </Section>
      </div>
    </div>
  );
}
