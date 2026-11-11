import { ArrowRight, ExternalLink, FlaskConical, ShieldCheck } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { inputClass } from "@/components/action-form";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { EmptyState, PageHeader, Panel, Section, Stat } from "@/components/page";
import { Badge, CriticalityBadge, RoleBadge, SeverityBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { attempt } from "@/lib/attempt";
import { api } from "@/lib/relay-api";
import type { ExposedRisk, SimulatedResponsibility, SimulationView } from "@/lib/types";
import { cn } from "@/lib/utils";

export const metadata: Metadata = { title: "What-if simulator" };

const RISK_LABEL: Record<ExposedRisk["kind"], string> = {
  uncovered: "No cover",
  single_holder: "Single holder",
  undocumented: "Undocumented",
  stale_knowledge: "Stale knowledge",
};

const one = (v: string | string[] | undefined) => (typeof v === "string" && v ? v : undefined);

export default async function SimulatorPage({
  params,
  searchParams,
}: PageProps<"/w/[workspaceId]/simulator">) {
  const [{ workspaceId }, query] = await Promise.all([params, searchParams]);
  const personId = one(query.person);
  const backupId = one(query.backup);
  const [people, result] = await Promise.all([
    attempt(api.listPeople(workspaceId)),
    personId ? attempt(api.simulation(workspaceId, personId, backupId)) : null,
  ]);
  if (!people.ok) return <ApiErrorNotice error={people.error} />;
  const active = people.data.filter((p) => p.status === "active");

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader
        title="What-if simulator"
        description="See what breaks if someone becomes unavailable, before it happens. Nothing is changed."
      />
      <div className="flex w-full max-w-6xl flex-col gap-6 p-6">
        <Panel className="p-4">
          <form method="get" className="grid items-end gap-3 md:grid-cols-[1fr_1fr_auto]">
            <label className="flex flex-col gap-1.5 text-xs font-medium">
              If this person became unavailable
              <select name="person" defaultValue={personId ?? ""} required className={inputClass}>
                <option value="" disabled>
                  Choose a person…
                </option>
                {active.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.display_name}
                    {p.title ? ` · ${p.title}` : ""}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1.5 text-xs font-medium">
              …and this person stepped in as backup (optional)
              <select name="backup" defaultValue={backupId ?? ""} className={inputClass}>
                <option value="">Nobody: show the raw impact</option>
                {active
                  .filter((p) => p.id !== personId)
                  .map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.display_name}
                    </option>
                  ))}
              </select>
            </label>
            <Button type="submit">
              <FlaskConical aria-hidden />
              Run simulation
            </Button>
          </form>
        </Panel>

        {result === null ? (
          <EmptyState
            title="Pick someone to test your readiness"
            description="Relay recomputes coverage as if they were away: what loses its owner, what work is left without cover, and which new single points of failure appear. Add a backup to compare."
          />
        ) : !result.ok ? (
          <ApiErrorNotice error={result.error} />
        ) : (
          <Results workspaceId={workspaceId} view={result.data} />
        )}
      </div>
    </div>
  );
}

function Results({ workspaceId, view }: { workspaceId: string; view: SimulationView }) {
  const affected = view.affected_responsibilities;
  const uncovered = view.uncovered_responsibilities.length;
  const scoreTone = (n: number) => (n >= 80 ? "success" : n >= 50 ? "warning" : "danger");
  if (affected.length === 0) {
    return (
      <EmptyState
        title={`${view.person.name} holds no responsibilities`}
        description="Nothing would lose its owner. Their open work, if any, is listed on their profile."
      />
    );
  }
  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <ReadinessStat view={view} tone={scoreTone(view.readiness_score)} />
        <Stat
          label="Responsibilities affected"
          value={affected.length}
          hint={`${affected.filter((s) => s.criticality === "critical").length} critical`}
        />
        <Stat
          label="Left without cover"
          value={uncovered}
          tone={uncovered ? "danger" : "success"}
          hint={
            view.backup
              ? `${view.covered_by_backup.length} covered by ${view.backup.name}`
              : "No backup applied"
          }
        />
        <Stat
          label="Open work without cover"
          value={view.open_work_without_cover.length}
          tone={view.open_work_without_cover.length ? "warning" : "default"}
          hint={`${view.orphaned_knowledge_count} knowledge items lose their keeper`}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
        <Section
          title="What changes"
          description={`Coverage of everything ${view.person.name} holds, recomputed without them.`}
        >
          <Panel className="overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 text-muted-foreground text-left text-xs">
                <tr>
                  <th className="px-4 py-2 font-medium">Responsibility</th>
                  <th className="px-4 py-2 font-medium">Their role</th>
                  <th className="px-4 py-2 font-medium">After</th>
                  <th className="hidden px-4 py-2 font-medium md:table-cell">Knowledge</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {affected.map((s) => (
                  <Row key={s.responsibility_id} workspaceId={workspaceId} s={s} />
                ))}
              </tbody>
            </table>
          </Panel>
        </Section>

        <div className="flex flex-col gap-6">
          <Section title="Newly exposed" description="Gaps this absence would create or reveal.">
            {view.exposed_risks.length === 0 ? (
              <p className="text-muted-foreground flex items-center gap-2 text-sm">
                <ShieldCheck aria-hidden className="size-4 text-emerald-600" />
                No new gaps.
              </p>
            ) : (
              <ul className="flex flex-col gap-2">
                {view.exposed_risks.map((r) => (
                  <li
                    key={`${r.kind}:${r.responsibility_id}`}
                    className="bg-card rounded-lg border px-3 py-2.5 text-sm shadow-xs"
                  >
                    <div className="flex items-center gap-2">
                      <SeverityBadge value={r.severity} />
                      <span className="text-muted-foreground text-xs">{RISK_LABEL[r.kind]}</span>
                    </div>
                    <p className="mt-1 font-medium">{r.responsibility_name}</p>
                    <p className="text-muted-foreground text-xs">{r.detail}</p>
                  </li>
                ))}
              </ul>
            )}
          </Section>

          {view.existing_risks.length > 0 ? (
            <Section title="Already open" description="Risks recorded on these today.">
              <ul className="flex flex-col gap-1.5 text-sm">
                {view.existing_risks.map((r) => (
                  <li key={r.key} className="flex items-start gap-2">
                    <SeverityBadge value={r.severity} />
                    <span>{r.title}</span>
                  </li>
                ))}
              </ul>
            </Section>
          ) : null}
        </div>
      </div>

      <Section
        title="Open work that would stall"
        description={`Assigned to ${view.person.name}, in places nobody else would cover. ${view.open_work_total} open items in total.`}
      >
        {view.open_work_without_cover.length === 0 ? (
          <p className="text-muted-foreground text-sm">Nothing uncovered.</p>
        ) : (
          <Panel>
            <ul className="divide-y text-sm">
              {view.open_work_without_cover.map((w, i) => (
                <li key={`${w.source}-${i}`} className="flex items-center gap-3 px-4 py-2.5">
                  <Badge tone="muted" className="w-20 justify-center">
                    {w.source}
                  </Badge>
                  <span className="min-w-0 flex-1 truncate">{w.title}</span>
                  {w.url ? (
                    <a
                      href={w.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-muted-foreground hover:text-foreground"
                      aria-label={`Open ${w.title}`}
                    >
                      <ExternalLink aria-hidden className="size-3.5" />
                    </a>
                  ) : null}
                </li>
              ))}
            </ul>
          </Panel>
        )}
      </Section>

      <Panel className="flex flex-col gap-3 p-4 text-sm md:flex-row md:items-center">
        <div className="min-w-0 flex-1">
          <p className="font-medium">Simulation only. Nothing in the workspace was changed.</p>
          <p className="text-muted-foreground text-xs">How the score works: {view.score_basis}</p>
        </div>
        <Link
          href={`/w/${workspaceId}/cases/new?type=departure`}
          className="text-primary inline-flex items-center gap-1 text-sm font-medium hover:underline"
        >
          Plan a real handover
          <ArrowRight aria-hidden className="size-3.5" />
        </Link>
      </Panel>
    </div>
  );
}

function ReadinessStat({
  view,
  tone,
}: {
  view: SimulationView;
  tone: "success" | "warning" | "danger";
}) {
  const bar = { success: "bg-emerald-600", warning: "bg-amber-500", danger: "bg-red-600" }[tone];
  const delta = view.readiness_score - view.baseline_score;
  return (
    <div className="bg-card flex flex-col gap-2 rounded-lg border px-4 py-3 shadow-xs">
      <span className="text-muted-foreground text-xs font-medium">Continuity readiness</span>
      <span className="flex items-baseline gap-2">
        <span className="tabular text-2xl leading-none font-semibold">{view.readiness_score}</span>
        <span className="text-muted-foreground text-xs">/ 100</span>
        {view.backup && delta !== 0 ? (
          <span className="tabular text-xs font-medium text-emerald-700 dark:text-emerald-300">
            +{delta} with {view.backup.name.split(" ")[0]}
          </span>
        ) : null}
      </span>
      <div className="bg-muted relative h-1.5 overflow-hidden rounded-full" aria-hidden>
        {view.backup ? (
          <div
            className="bg-foreground/15 absolute inset-y-0 left-0"
            style={{ width: `${view.readiness_score}%` }}
          />
        ) : null}
        <div
          className={cn("absolute inset-y-0 left-0 rounded-full", bar)}
          style={{ width: `${view.backup ? view.baseline_score : view.readiness_score}%` }}
        />
        {view.backup ? (
          <div
            className="absolute inset-y-0 rounded-r-full bg-emerald-600/70"
            style={{
              left: `${view.baseline_score}%`,
              width: `${Math.max(0, delta)}%`,
            }}
          />
        ) : null}
      </div>
    </div>
  );
}

function Row({ workspaceId, s }: { workspaceId: string; s: SimulatedResponsibility }) {
  return (
    <tr className={cn(s.cover === "uncovered" && "bg-red-50/60 dark:bg-red-950/20")}>
      <td className="px-4 py-2.5">
        <Link
          href={`/w/${workspaceId}/responsibilities/${s.responsibility_id}`}
          className="font-medium hover:underline"
        >
          {s.name}
        </Link>
        <div className="mt-1">
          <CriticalityBadge value={s.criticality} />
        </div>
      </td>
      <td className="px-4 py-2.5">
        <RoleBadge value={s.role} />
      </td>
      <td className="px-4 py-2.5">
        {s.cover === "uncovered" ? (
          <span className="text-destructive font-medium">Nobody</span>
        ) : (
          <span className="flex flex-col">
            <span>
              {s.covered_by?.name}
              {s.cover === "covered_by_backup" ? (
                <Badge tone="warning" className="ml-1.5">
                  Simulated
                </Badge>
              ) : null}
            </span>
            <span className="text-muted-foreground text-xs">
              {s.single_holder_after ? "Becomes the only holder" : "Shared cover remains"}
            </span>
          </span>
        )}
      </td>
      <td className="text-muted-foreground hidden px-4 py-2.5 text-xs md:table-cell">
        {s.knowledge_total === 0 ? (
          <span className="text-destructive">None recorded</span>
        ) : (
          `${s.knowledge_total} item${s.knowledge_total === 1 ? "" : "s"}${
            s.knowledge_stale ? `, ${s.knowledge_stale} stale` : ""
          }`
        )}
      </td>
    </tr>
  );
}
