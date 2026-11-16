import {
  ArrowRight,
  CalendarClock,
  ChevronRight,
  Download,
  ExternalLink,
  FlaskConical,
  Pin,
  PinOff,
  ShieldCheck,
  Users,
} from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";

import { inputClass } from "@/components/action-form";
import { Explain } from "@/components/explain";
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
  ScoreParts,
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

/** A pinned scenario travels in the URL as `person:backup:days` (backup and days optional). */
type Pinned = { key: string; person: string; backup?: string; days?: string };
const MAX_PINS = 3;

function readPins(v: string | string[] | undefined): Pinned[] {
  const raw = typeof v === "string" ? [v] : (v ?? []);
  const pins: Pinned[] = [];
  for (const key of raw) {
    const [person, backup, days] = key.split(":");
    if (!person || pins.some((p) => p.key === key)) continue;
    pins.push({ key, person, backup: backup || undefined, days: days || undefined });
  }
  return pins.slice(0, MAX_PINS);
}

export default async function SimulatorPage({
  params,
  searchParams,
}: PageProps<"/w/[workspaceId]/simulator">) {
  const [{ workspaceId }, query] = await Promise.all([params, searchParams]);
  const personId = one(query.person);
  const backupId = one(query.backup);
  const days = one(query.days);
  const pins = readPins(query.pin);
  const [people, result, candidates, pinned] = await Promise.all([
    attempt(api.listPeople(workspaceId)),
    personId ? attempt(api.simulation(workspaceId, personId, backupId, days)) : null,
    personId ? attempt(api.simulationCandidates(workspaceId, personId, days)) : null,
    // A pin whose person was removed shows "Couldn't load" rather than failing the page.
    Promise.all(
      pins.map((p) => api.simulation(workspaceId, p.person, p.backup, p.days).catch(() => null)),
    ),
  ]);
  // Every link keeps the pinned scenarios, so comparing never loses what was pinned.
  const href = (scene: { person?: string; backup?: string; days?: string }, keep: string[]) => {
    const q = new URLSearchParams();
    if (scene.person) q.set("person", scene.person);
    if (scene.days) q.set("days", scene.days);
    if (scene.backup) q.set("backup", scene.backup);
    for (const key of keep) q.append("pin", key);
    return `?${q}`;
  };
  const pinKeys = pins.map((p) => p.key);
  const scenario = (backup?: string) => href({ person: personId, backup, days }, pinKeys);
  const currentKey = personId ? `${personId}:${backupId ?? ""}:${days ?? ""}` : null;
  const isPinned = currentKey !== null && pinKeys.includes(currentKey);
  if (!people.ok) return <ApiErrorNotice error={people.error} />;
  const active = people.data.filter((p) => p.status === "active");

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader
        title={
          <span className="flex items-center gap-1.5">
            What-if simulator <Explain what="simulation" align="start" />
          </span>
        }
        description="See what breaks if someone becomes unavailable, before it happens. Nothing is changed."
      />
      <div className="flex w-full flex-col gap-6 p-6">
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
            {pinKeys.map((key) => (
              <input key={key} type="hidden" name="pin" value={key} />
            ))}
            <Button type="submit">
              <FlaskConical aria-hidden />
              Run simulation
            </Button>
          </form>
        </Panel>

        {pins.length > 0 ? (
          <Comparison
            pins={pins}
            views={pinned}
            names={new Map(people.data.map((p) => [p.id, p.display_name]))}
            open={(p) => href(p, pinKeys)}
            unpin={(key) =>
              href(
                { person: personId, backup: backupId, days },
                pinKeys.filter((k) => k !== key),
              )
            }
          />
        ) : null}

        {result === null ? (
          <EmptyState
            title="Pick someone to test your readiness"
            description="Relay recomputes coverage as if they were away: what loses its owner, what work is left without cover, and which new single points of failure appear. Add a backup to compare."
          />
        ) : !result.ok ? (
          <ApiErrorNotice error={result.error} />
        ) : (
          <>
            <div className="-mb-3 flex flex-wrap items-center justify-end gap-x-5 gap-y-2">
              {isPinned ? (
                <span className="text-muted-foreground inline-flex items-center gap-1.5 text-sm">
                  <Pin aria-hidden className="size-4" />
                  Pinned for comparison
                </span>
              ) : currentKey && pins.length < MAX_PINS ? (
                <Link
                  href={href({ person: personId, backup: backupId, days }, [
                    ...pinKeys,
                    currentKey,
                  ])}
                  scroll={false}
                  className="text-primary inline-flex items-center gap-1.5 text-sm font-medium hover:underline"
                >
                  <Pin aria-hidden className="size-4" />
                  Pin to compare ({pins.length}/{MAX_PINS})
                </Link>
              ) : (
                <span className="text-muted-foreground text-sm">
                  {MAX_PINS} scenarios pinned: unpin one to add this
                </span>
              )}
              {result.data.affected_responsibilities.length > 0 ? (
                <a
                  href={`/w/${workspaceId}/simulator/report${scenario(backupId)}`}
                  download
                  className="text-primary inline-flex items-center gap-1.5 text-sm font-medium hover:underline"
                >
                  <Download aria-hidden className="size-4" />
                  Download scenario report (with every candidate compared)
                </a>
              ) : null}
            </div>
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

const DAYS_LABEL: Record<string, string> = {
  "3": "3 days",
  "7": "1 week",
  "14": "2 weeks",
  "30": "1 month",
  "90": "3 months",
};

const COMPARED: { label: string; value: (v: SimulationView) => number; higherIsBetter: boolean }[] =
  [
    { label: "Readiness score", value: (v) => v.readiness_score, higherIsBetter: true },
    {
      label: "Responsibilities affected",
      value: (v) => v.affected_responsibilities.length,
      higherIsBetter: false,
    },
    {
      label: "Left without an owner",
      value: (v) => v.uncovered_responsibilities.length,
      higherIsBetter: false,
    },
    { label: "New risks exposed", value: (v) => v.exposed_risks.length, higherIsBetter: false },
    {
      label: "Open work without cover",
      value: (v) => v.open_work_without_cover.length,
      higherIsBetter: false,
    },
    {
      label: "Knowledge left orphaned",
      value: (v) => v.orphaned_knowledge_count,
      higherIsBetter: false,
    },
  ];

/** Pinned scenarios side by side. The best value in each row is marked so differences stand out. */
function Comparison({
  pins,
  views,
  names,
  open,
  unpin,
}: {
  pins: Pinned[];
  views: (SimulationView | null)[];
  names: Map<string, string>;
  open: (p: Pinned) => string;
  unpin: (key: string) => string;
}) {
  return (
    <Section
      title="Pinned scenarios"
      description="Up to three what-ifs side by side. The best value in each row is highlighted."
    >
      <Panel className="overflow-x-auto">
        <table className="w-full min-w-[34rem] text-sm">
          <thead>
            <tr className="border-b text-left">
              <th scope="col" className="text-muted-foreground p-3 font-medium">
                Scenario
              </th>
              {pins.map((p) => (
                <th key={p.key} scope="col" className="p-3 align-top font-medium">
                  <Link href={open(p)} className="hover:underline">
                    {names.get(p.person) ?? "Unknown person"} away
                  </Link>
                  <span className="text-muted-foreground block text-xs font-normal">
                    {p.days ? (DAYS_LABEL[p.days] ?? `${p.days} days`) : "Open-ended"} ·{" "}
                    {p.backup ? `covered by ${names.get(p.backup) ?? "unknown"}` : "no cover"}
                  </span>
                  <Link
                    href={unpin(p.key)}
                    scroll={false}
                    className="text-muted-foreground hover:text-foreground mt-1 inline-flex items-center gap-1 text-xs font-normal"
                  >
                    <PinOff aria-hidden className="size-3" />
                    Unpin
                  </Link>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {COMPARED.map((row) => {
              const values = views.map((v) => (v ? row.value(v) : null));
              const known = values.filter((n): n is number => n !== null);
              const best =
                known.length > 1 ? (row.higherIsBetter ? Math.max : Math.min)(...known) : null;
              const tie = best !== null && known.every((n) => n === best);
              return (
                <tr key={row.label} className="border-b last:border-0">
                  <th scope="row" className="text-muted-foreground p-3 text-left font-normal">
                    {row.label}
                  </th>
                  {values.map((n, i) => (
                    <td
                      key={pins[i].key}
                      className={cn(
                        "p-3 tabular-nums",
                        n !== null &&
                          n === best &&
                          !tie &&
                          "font-semibold text-emerald-700 dark:text-emerald-400",
                      )}
                    >
                      {n ?? (
                        <span className="text-muted-foreground text-xs">Couldn&apos;t load</span>
                      )}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </Panel>
    </Section>
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

          {view.downstream?.length ? (
            <Section
              title="Downstream impact"
              description="Work that depends on something left with nobody, followed through the recorded dependencies."
            >
              <ul className="flex flex-col gap-2">
                {view.downstream.map((d) => (
                  <li
                    key={d.responsibility_id}
                    className="bg-card rounded-lg border px-3 py-2.5 text-sm shadow-xs"
                  >
                    <p className="font-medium">
                      {d.name}{" "}
                      <span className="text-muted-foreground text-xs font-normal capitalize">
                        {d.criticality}
                      </span>
                    </p>
                    <p className="text-muted-foreground text-xs">
                      Depends on {d.via}
                      {d.depth > 1 ? `, which leads back to ${d.root}` : ""} (no cover).
                    </p>
                  </li>
                ))}
              </ul>
            </Section>
          ) : null}

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
      <span className="text-muted-foreground flex items-center gap-1 text-xs font-medium">
        Continuity readiness
        <Explain
          what="readiness"
          align="start"
          working={
            view.score_parts ? (
              <ReadinessWorking parts={view.score_parts} score={view.readiness_score} />
            ) : null
          }
        />
      </span>
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
      {view.score_parts ? <ScoreWorking parts={view.score_parts} /> : null}
    </div>
  );
}

const PARTS = [
  { key: "cover_weight", label: "Someone covers it", share: 60 },
  { key: "knowledge_weight", label: "Usable knowledge", share: 25 },
  { key: "second_holder_weight", label: "Second holder", share: 15 },
] as const;

/** The score's working, always visible: each part, how much of it is met, and its points. */
/** Row by row: which affected responsibilities earn which part, then the arithmetic. */
function ReadinessWorking({ parts, score }: { parts: ScoreParts; score: number }) {
  const yes = (v: boolean) => (v ? "✓" : "–");
  return (
    <>
      <table className="w-full text-[11px]">
        <thead className="text-muted-foreground">
          <tr>
            <th className="py-0.5 text-left font-medium">Responsibility</th>
            <th className="font-medium">Weight</th>
            <th className="font-medium">Cover</th>
            <th className="font-medium">Knowledge</th>
            <th className="font-medium">2nd holder</th>
          </tr>
        </thead>
        <tbody className="tabular text-center">
          {parts.rows.map((r) => (
            <tr key={r.responsibility_id}>
              <td className="max-w-28 truncate py-0.5 text-left">{r.name}</td>
              <td>
                {r.weight} <span className="text-muted-foreground">({r.criticality})</span>
              </td>
              <td>{yes(r.covered)}</td>
              <td>{yes(r.knowledge)}</td>
              <td>{yes(r.second_holder)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <span className="tabular">
        Cover {parts.cover_weight}/{parts.possible} × 60 + knowledge {parts.knowledge_weight}/
        {parts.possible} × 25 + 2nd holder {parts.second_holder_weight}/{parts.possible} × 15 ={" "}
        <strong className="text-foreground">{score}</strong>
      </span>
    </>
  );
}

function ScoreWorking({ parts }: { parts: ScoreParts }) {
  return (
    <dl className="mt-1 flex flex-col gap-1.5 border-t pt-2 text-[11px]">
      {PARTS.map((p, i) => {
        const met = parts[p.key] / parts.possible;
        return (
          <div key={p.key} className="grid grid-cols-[1fr_auto] items-center gap-x-2 gap-y-0.5">
            <dt className="text-muted-foreground">
              {p.label} <span className="opacity-70">· {p.share}%</span>
            </dt>
            <dd className="tabular font-medium">
              {Math.round(met * p.share)} / {p.share}
            </dd>
            <div className="bg-muted col-span-2 h-1 overflow-hidden rounded-full" aria-hidden>
              <div
                className="bar-grow bg-foreground/60 h-full rounded-full"
                style={{ width: `${met * 100}%`, animationDelay: `${i * 70}ms` }}
              />
            </div>
          </div>
        );
      })}
      <p className="text-muted-foreground">
        Weighted by criticality across {parts.possible} weight points of affected work.
      </p>
    </dl>
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
          ? "-"
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
                      {c.overloaded ? <Explain what="overload" className="ml-1" /> : null}
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
