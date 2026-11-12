import {
  ArrowRight,
  CalendarClock,
  ChevronRight,
  ExternalLink,
  FlaskConical,
  ShieldCheck,
  Users,
} from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { inputClass } from "@/components/action-form";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { EmptyState, PageHeader, Panel, Section, Stat } from "@/components/page";
import { Badge, CriticalityBadge, RoleBadge, SeverityBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { attempt } from "@/lib/attempt";
import { api } from "@/lib/relay-api";
import { Avatar } from "@/components/visual";
import type {
  CandidatesView,
  ExposedRisk,
  SimulatedResponsibility,
  SimulationView,
} from "@/lib/types";
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
  const days = one(query.days);
  const [people, result, candidates] = await Promise.all([
    attempt(api.listPeople(workspaceId)),
    personId ? attempt(api.simulation(workspaceId, personId, backupId, days)) : null,
    personId ? attempt(api.simulationCandidates(workspaceId, personId, days)) : null,
  ]);
  const scenario = (backup?: string) =>
    `?${new URLSearchParams({
      person: personId ?? "",
      ...(days ? { days } : {}),
      ...(backup ? { backup } : {}),
    })}`;
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
          <form
            method="get"
            data-tour="simulator-form"
            className="grid items-end gap-3 md:grid-cols-[1.3fr_0.8fr_1.2fr_auto]"
          >
            <label className="flex flex-col gap-1.5 text-xs font-medium">
              What if
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
              is unavailable for
              <select name="days" defaultValue={days ?? ""} className={inputClass}>
                <option value="">An open-ended period</option>
                <option value="3">3 days</option>
                <option value="7">1 week</option>
                <option value="14">2 weeks</option>
                <option value="30">1 month</option>
                <option value="90">3 months</option>
              </select>
            </label>
            <label className="flex flex-col gap-1.5 text-xs font-medium">
              and is covered by
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
          <>
            <Results workspaceId={workspaceId} view={result.data} />
            {candidates?.ok && result.data.affected_responsibilities.length > 0 ? (
              <Candidates view={candidates.data} current={backupId} link={scenario} />
            ) : null}
          </>
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
          hint={
            view.days
              ? `${view.due_in_window} due within ${view.days} days`
              : `${view.orphaned_knowledge_count} knowledge items lose their keeper`
          }
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
                  {w.due_in_window ? (
                    <Badge tone="warning" className="gap-1">
                      <CalendarClock aria-hidden className="size-3" />
                      Due while away
                    </Badge>
                  ) : null}
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
          href={`/w/${workspaceId}/cases/new?type=${view.days ? "coverage" : "departure"}&person=${view.person.id}`}
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
        <div className="mt-1 flex flex-wrap items-center gap-1.5">
          <CriticalityBadge value={s.criticality} />
          {s.assets.map((a) => (
            <Badge key={a} tone="muted">
              {a}
            </Badge>
          ))}
        </div>
        {s.reasons.length ? (
          <details className="group mt-1.5 text-xs">
            <summary className="text-muted-foreground hover:text-foreground flex cursor-pointer list-none items-center gap-1 select-none">
              <ChevronRight
                aria-hidden
                className="size-3 transition-transform group-open:rotate-90"
              />
              Why it is affected
            </summary>
            <ul className="text-muted-foreground mt-1 flex flex-col gap-0.5 border-l pl-3">
              {s.reasons.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          </details>
        ) : null}
        <Link
          href={`/w/${workspaceId}/responsibilities/${s.responsibility_id}/timeline`}
          className="text-primary mt-1 inline-block text-xs hover:underline"
        >
          See its history
        </Link>
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

function Candidates({
  view,
  current,
  link,
}: {
  view: CandidatesView;
  current?: string;
  link: (backup?: string) => string;
}) {
  const rows: { label: string; value: (c: CandidatesView["candidates"][number]) => string }[] = [
    {
      label: "Responsibilities with someone holding them",
      value: (c) => `${c.covered} of ${c.total}`,
    },
    { label: "Critical or high left with nobody", value: (c) => String(c.critical_gaps) },
    { label: "Without usable knowledge", value: (c) => String(c.knowledge_gaps) },
    { label: "Gaps remaining", value: (c) => String(c.remaining_risks) },
    { label: "Readiness", value: (c) => `${c.readiness_score} / 100` },
    {
      label: "Responsibilities they would hold",
      value: (c) =>
        c.load_after === null
          ? "—"
          : `${c.load_after}${c.overloaded ? ` · overloaded (typical ${view.typical_load})` : ""}`,
    },
  ];
  return (
    <Section
      title="Who could cover?"
      description={`Each option is simulated with the same scenario. ${view.basis}`}
    >
      {view.candidates.length === 1 ? (
        <p className="text-muted-foreground flex items-center gap-2 text-sm">
          <Users aria-hidden className="size-4" />
          Nobody is connected to this work yet: no team-mates, co-owners or backups to suggest.
        </p>
      ) : (
        <Panel className="overflow-x-auto">
          <table className="w-full min-w-[40rem] text-sm">
            <thead>
              <tr className="border-b">
                <th className="text-muted-foreground w-56 px-4 py-3 text-left text-xs font-medium">
                  Option
                </th>
                {view.candidates.map((c) => {
                  const selected = c.person ? c.person.id === current : !current;
                  return (
                    <th
                      key={c.person?.id ?? "nobody"}
                      className={cn(
                        "px-4 py-3 text-left align-top font-normal",
                        selected && "bg-accent/60",
                      )}
                    >
                      <div className="flex items-center gap-2">
                        {c.person ? <Avatar name={c.person.name} size="sm" /> : null}
                        <span className="font-medium">
                          {c.person ? c.person.name : "No replacement"}
                        </span>
                      </div>
                      <ul className="text-muted-foreground mt-1 flex flex-col gap-0.5 text-xs">
                        {c.signals.map((sig) => (
                          <li key={sig}>{sig}</li>
                        ))}
                      </ul>
                      {c.overloaded ? (
                        <span className="mt-1 inline-block rounded bg-amber-50 px-1.5 py-0.5 text-xs font-medium text-amber-800 dark:bg-amber-950/40 dark:text-amber-300">
                          Would be overloaded
                        </span>
                      ) : null}
                      {c.person && !selected ? (
                        <Link
                          href={link(c.person.id)}
                          className="text-primary mt-1.5 inline-block text-xs font-medium hover:underline"
                        >
                          Simulate with {c.person.name.split(" ")[0]}
                        </Link>
                      ) : selected ? (
                        <span className="text-accent-foreground mt-1.5 inline-block text-xs font-medium">
                          Shown above
                        </span>
                      ) : null}
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody className="divide-y">
              {rows.map((r) => (
                <tr key={r.label}>
                  <td className="text-muted-foreground px-4 py-2.5 text-xs">{r.label}</td>
                  {view.candidates.map((c) => {
                    const selected = c.person ? c.person.id === current : !current;
                    return (
                      <td
                        key={c.person?.id ?? "nobody"}
                        className={cn(
                          "tabular px-4 py-2.5 font-medium",
                          selected && "bg-accent/60",
                        )}
                      >
                        {r.value(c)}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>
      )}
    </Section>
  );
}
