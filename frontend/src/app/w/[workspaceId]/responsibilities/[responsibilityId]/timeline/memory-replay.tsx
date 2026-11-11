"use client";

import {
  BookOpenText,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  Link2,
  Pause,
  Play,
  MessageSquareText,
  PanelRight,
  RotateCcw,
  SendHorizontal,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState, useTransition } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { inputClass } from "@/components/action-form";
import type {
  HistoryAnswer,
  NarrativeView,
  TimelineCategory,
  TimelineEvent,
  TimelineView,
} from "@/lib/types";
import { cn } from "@/lib/utils";

import { askHistoryAction, narrateTimelineAction } from "./actions";

const CATEGORY: Record<TimelineCategory, { label: string; dot: string }> = {
  incident: { label: "Incident", dot: "bg-red-600" },
  bug_fix: { label: "Bug fix", dot: "bg-amber-500" },
  decision: { label: "Decision", dot: "bg-primary" },
  ownership_change: { label: "Ownership", dot: "bg-sky-600" },
  implementation: { label: "Implementation", dot: "bg-emerald-600" },
  technical_change: { label: "Technical change", dot: "bg-slate-500" },
  documentation: { label: "Documentation", dot: "bg-slate-300 dark:bg-slate-500" },
};
const ORDER = Object.keys(CATEGORY) as TimelineCategory[];
const BASIS = {
  label: "Category from the source's labels",
  title: "Category inferred from the title",
  record: "Recorded in Relay",
  default: "No label: shown as implementation",
};

const month = new Intl.DateTimeFormat("en-GB", { month: "long", year: "numeric" });
const day = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short" });
const short = new Intl.DateTimeFormat("en-GB", { month: "short", year: "numeric" });

export function MemoryReplay({
  workspaceId,
  timeline,
  stored,
}: {
  workspaceId: string;
  timeline: TimelineView;
  /** The last persisted reading (already filtered to what this viewer may see). */
  stored: NarrativeView | null;
}) {
  const [filter, setFilter] = useState<TimelineCategory | null>(null);
  const [cursor, setCursor] = useState<number | null>(null); // replay position, oldest = 0
  const [playing, setPlaying] = useState(false);
  const [focus, setFocus] = useState<Set<string>>(new Set());
  const [narrative, setNarrative] = useState<NarrativeView | null>(stored);
  const [selected, setSelected] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();
  const rows = useRef(new Map<string, HTMLLIElement>());

  const chronological = useMemo(() => [...timeline.events].reverse(), [timeline.events]);
  const byId = useMemo(() => new Map(timeline.events.map((e) => [e.id, e])), [timeline.events]);

  useEffect(() => {
    if (!playing) return;
    const timer = setInterval(() => {
      setCursor((c) => {
        const next = (c ?? -1) + 1;
        if (next >= chronological.length - 1) setPlaying(false);
        return Math.min(next, chronological.length - 1);
      });
    }, 900);
    return () => clearInterval(timer);
  }, [playing, chronological.length]);

  const current = cursor === null ? null : chronological[cursor];
  const shown = timeline.events.filter((e) => {
    if (filter && e.category !== filter) return false;
    if (current && e.occurred_at > current.occurred_at) return false;
    if (current && e.occurred_at === current.occurred_at && e.id > current.id) return false;
    return true;
  });
  const groups = groupByMonth(shown);

  function jump(ids: string[]) {
    setFocus(new Set(ids));
    if (ids.length === 1) setSelected(ids[0]);
    setFilter(null);
    setCursor(null);
    setPlaying(false);
    requestAnimationFrame(() =>
      rows.current.get(ids[0])?.scrollIntoView({ behavior: "smooth", block: "center" }),
    );
  }

  function explain() {
    setError(null);
    startTransition(async () => {
      const result = await narrateTimelineAction(workspaceId, timeline.responsibility_id);
      if (result.error) setError(result.error);
      else setNarrative(result.narrative ?? null);
    });
  }

  if (timeline.events.length === 0) {
    return (
      <div className="p-6">
        <div className="bg-card/50 flex flex-col items-center rounded-lg border border-dashed px-6 py-12 text-center">
          <p className="font-medium">No history yet</p>
          <p className="text-muted-foreground mt-1 max-w-md text-sm">
            Link a GitHub repository, Linear project or Notion page to this responsibility, or
            record decisions and owners, and its history appears here.
          </p>
          <SourceLine timeline={timeline} />
        </div>
      </div>
    );
  }

  return (
    <div className="grid gap-6 p-6 xl:grid-cols-[minmax(0,1fr)_24rem]">
      <div className="flex min-w-0 flex-col gap-4">
        <div className="bg-card flex flex-col gap-3 rounded-lg border p-3 shadow-xs">
          <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter by category">
            <Chip active={filter === null} onClick={() => setFilter(null)}>
              All <span className="tabular text-muted-foreground">{timeline.total}</span>
            </Chip>
            {ORDER.filter((c) => timeline.counts[c] > 0).map((c) => (
              <Chip key={c} active={filter === c} onClick={() => setFilter(c)}>
                <span aria-hidden className={cn("size-2 rounded-full", CATEGORY[c].dot)} />
                {CATEGORY[c].label}
                <span className="tabular text-muted-foreground">{timeline.counts[c]}</span>
              </Chip>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-2 border-t pt-3">
            <Button
              size="sm"
              variant={playing ? "outline" : "default"}
              onClick={() => {
                if (!playing && (cursor === null || cursor >= chronological.length - 1))
                  setCursor(0);
                setPlaying(!playing);
              }}
            >
              {playing ? <Pause aria-hidden /> : <Play aria-hidden />}
              {playing ? "Pause" : cursor === null ? "Replay history" : "Resume"}
            </Button>
            <Button
              size="icon-sm"
              variant="ghost"
              aria-label="Previous event"
              disabled={cursor === null || cursor === 0}
              onClick={() => {
                setPlaying(false);
                setCursor((c) => Math.max(0, (c ?? 0) - 1));
              }}
            >
              <ChevronLeft aria-hidden />
            </Button>
            <Button
              size="icon-sm"
              variant="ghost"
              aria-label="Next event"
              disabled={cursor !== null && cursor >= chronological.length - 1}
              onClick={() => {
                setPlaying(false);
                setCursor((c) => Math.min(chronological.length - 1, (c ?? -1) + 1));
              }}
            >
              <ChevronRight aria-hidden />
            </Button>
            <input
              type="range"
              min={0}
              max={chronological.length - 1}
              value={cursor ?? chronological.length - 1}
              onChange={(e) => {
                setPlaying(false);
                setCursor(Number(e.target.value));
              }}
              aria-label="Replay position"
              className="accent-primary min-w-32 flex-1"
            />
            <span className="text-muted-foreground tabular w-28 text-right text-xs">
              {current
                ? day.format(new Date(current.occurred_at)) +
                  " " +
                  new Date(current.occurred_at).getFullYear()
                : "Today"}
            </span>
            {cursor !== null ? (
              <Button
                size="icon-sm"
                variant="ghost"
                aria-label="Back to today"
                onClick={() => {
                  setPlaying(false);
                  setCursor(null);
                }}
              >
                <RotateCcw aria-hidden />
              </Button>
            ) : null}
          </div>
        </div>

        <ChapterAxis
          events={chronological}
          narrative={narrative?.state === "ready" ? narrative : null}
          current={current?.id ?? null}
          onSelect={(id) => jump([id])}
          onChapter={(ids) => jump(ids)}
        />

        {groups.length === 0 ? (
          <p className="text-muted-foreground px-1 text-sm">No events in this view.</p>
        ) : (
          <div role="region" aria-label="Events" className="flex flex-col gap-4">
            {groups.map(([label, events]) => (
              <section key={label} aria-label={label}>
                <h2 className="bg-background/90 text-muted-foreground sticky top-14 z-[1] py-1.5 text-xs font-semibold tracking-wide uppercase backdrop-blur">
                  {label}
                </h2>
                <ol className="relative ml-2 border-l pl-5">
                  {events.map((e) => (
                    <EventRow
                      key={e.id}
                      event={e}
                      byId={byId}
                      current={current?.id === e.id}
                      focused={focus.has(e.id)}
                      onJump={jump}
                      onInspect={() => setSelected(e.id)}
                      inspected={selected === e.id}
                      register={(el) => {
                        if (el) rows.current.set(e.id, el);
                        else rows.current.delete(e.id);
                      }}
                    />
                  ))}
                </ol>
              </section>
            ))}
          </div>
        )}
        {timeline.truncated ? (
          <p className="text-muted-foreground text-xs">
            Showing the most recent {timeline.events.length} of {timeline.total} events.
          </p>
        ) : null}
      </div>

      <aside className="flex flex-col gap-4 xl:sticky xl:top-20 xl:max-h-[calc(100dvh-6rem)] xl:self-start xl:overflow-y-auto">
        {selected && byId.get(selected) ? (
          <EventInspector
            event={byId.get(selected)!}
            byId={byId}
            chapters={
              narrative?.state === "ready"
                ? narrative.chapters.filter((c) => c.event_ids.includes(selected))
                : []
            }
            onJump={jump}
            onClose={() => setSelected(null)}
          />
        ) : null}
        <div className="bg-card rounded-lg border p-4 shadow-xs">
          <p className="text-muted-foreground text-xs font-medium">Span</p>
          <p className="mt-1 text-sm font-medium">
            {timeline.first_at && timeline.last_at
              ? `${short.format(new Date(timeline.first_at))} to ${short.format(new Date(timeline.last_at))}`
              : "No dates"}
          </p>
          <SourceLine timeline={timeline} />
        </div>

        <div className="bg-card flex flex-col gap-3 rounded-lg border p-4 shadow-xs">
          <div>
            <h2 className="text-sm font-semibold">What this history means</h2>
            <p className="text-muted-foreground mt-0.5 text-xs">
              An AI reading of the events above. Every chapter cites the events it rests on;
              anything it couldn&apos;t cite is dropped.
            </p>
          </div>
          {narrative === null ? (
            <Button variant="outline" onClick={explain} disabled={pending} aria-busy={pending}>
              <BookOpenText aria-hidden />
              {pending ? "Reading the history…" : "Explain this history"}
            </Button>
          ) : (
            <>
              {narrative.outdated ? (
                <p
                  role="status"
                  className="rounded-md border border-amber-600/20 bg-amber-50 px-3 py-2 text-xs text-amber-950 dark:bg-amber-950/30 dark:text-amber-100"
                >
                  New events arrived after this reading was written. It may be incomplete.
                </p>
              ) : null}
              <Narrative narrative={narrative} byId={byId} onJump={jump} onRetry={explain} />
              {narrative.state === "ready" ? (
                <div className="text-muted-foreground flex items-center justify-between gap-2 border-t pt-2 text-xs">
                  <span>
                    Written {new Date(narrative.generated_at).toLocaleDateString("en-GB")}
                    {narrative.withheld
                      ? ` · ${narrative.withheld} chapter${narrative.withheld === 1 ? "" : "s"} withheld (sources you can't see)`
                      : ""}
                  </span>
                  <Button size="xs" variant="ghost" onClick={explain} disabled={pending}>
                    {pending ? "Rewriting…" : "Regenerate"}
                  </Button>
                </div>
              ) : null}
            </>
          )}
          {error ? (
            <p role="alert" className="text-destructive text-sm">
              {error}
            </p>
          ) : null}
        </div>

        <AskHistory
          workspaceId={workspaceId}
          responsibilityId={timeline.responsibility_id}
          byId={byId}
          onJump={jump}
        />

        <div className="text-muted-foreground flex flex-col gap-1.5 px-1 text-xs">
          <p>
            <Badge tone="neutral">Fact</Badge> Events come straight from the records: dates and
            sources are not interpreted.
          </p>
          <p>
            <Badge tone="warning">Inferred</Badge> Chapters and links between events are the
            AI&apos;s reading. Check the cited events before relying on them.
          </p>
        </div>
      </aside>
    </div>
  );
}

function SourceLine({ timeline }: { timeline: TimelineView }) {
  return (
    <ul className="text-muted-foreground mt-3 flex flex-wrap gap-x-3 gap-y-1 text-xs">
      {timeline.sources.map((s) => (
        <li key={s.source} className="flex items-center gap-1.5">
          <span
            aria-hidden
            className={cn(
              "size-1.5 rounded-full",
              s.state === "connected"
                ? "bg-emerald-600"
                : s.state === "partial"
                  ? "bg-amber-500"
                  : "bg-muted-foreground/40",
            )}
          />
          {s.source}{" "}
          {s.state === "connected"
            ? "connected"
            : s.state === "partial"
              ? "partial: history may be incomplete"
              : "not connected"}
        </li>
      ))}
    </ul>
  );
}

function Chip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-colors",
        active
          ? "border-primary/40 bg-accent text-accent-foreground font-medium"
          : "hover:bg-muted text-foreground/80",
      )}
    >
      {children}
    </button>
  );
}

function EventRow({
  event: e,
  byId,
  current,
  focused,
  onJump,
  onInspect,
  inspected,
  register,
}: {
  event: TimelineEvent;
  byId: Map<string, TimelineEvent>;
  current: boolean;
  focused: boolean;
  onJump: (ids: string[]) => void;
  onInspect: () => void;
  inspected: boolean;
  register: (el: HTMLLIElement | null) => void;
}) {
  const c = CATEGORY[e.category];
  return (
    <li ref={register} className="relative pb-4 last:pb-1">
      <span
        aria-hidden
        className={cn(
          "ring-background absolute top-3 -left-[25px] size-2.5 rounded-full ring-4",
          c.dot,
          e.significance === "high" && "-left-[26px] size-3",
        )}
      />
      <div
        className={cn(
          "bg-card rounded-lg border px-4 py-3 shadow-xs transition-shadow",
          current && "ring-primary/50 ring-2",
          focused && "ring-2 ring-amber-500/60",
        )}
      >
        <div className="text-muted-foreground flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
          <time dateTime={e.occurred_at} className="tabular text-foreground/80 font-medium">
            {day.format(new Date(e.occurred_at))}
          </time>
          <span aria-hidden>·</span>
          <span>{c.label}</span>
          <span aria-hidden>·</span>
          <span>{e.source_system}</span>
          {e.significance === "high" ? <Badge tone="neutral">Key event</Badge> : null}
          <button
            type="button"
            onClick={onInspect}
            aria-pressed={inspected}
            className={cn(
              "hover:bg-muted ml-auto inline-flex items-center gap-1 rounded px-1.5 py-0.5",
              inspected && "bg-accent text-accent-foreground",
            )}
          >
            <PanelRight aria-hidden className="size-3" />
            Inspect
          </button>
        </div>
        <p className="mt-1 text-sm font-medium">
          {e.source_url ? (
            <a
              href={e.source_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-start gap-1 hover:underline"
            >
              {e.title}
              <ExternalLink aria-hidden className="text-muted-foreground mt-1 size-3 shrink-0" />
            </a>
          ) : (
            e.title
          )}
        </p>
        <p className="text-muted-foreground mt-0.5 text-sm">{e.summary}</p>
        <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
          <span className="text-muted-foreground/80" title={BASIS[e.category_basis]}>
            {BASIS[e.category_basis]}
          </span>
          {e.linked_events
            .filter((id) => byId.has(id))
            .map((id) => (
              <button
                key={id}
                type="button"
                onClick={() => onJump([id])}
                className="text-primary inline-flex max-w-full items-center gap-1 hover:underline"
              >
                <Link2 aria-hidden className="size-3 shrink-0" />
                <span className="truncate">{byId.get(id)?.title}</span>
              </button>
            ))}
        </div>
      </div>
    </li>
  );
}

function Narrative({
  narrative,
  byId,
  onJump,
  onRetry,
}: {
  narrative: NarrativeView;
  byId: Map<string, TimelineEvent>;
  onJump: (ids: string[]) => void;
  onRetry: () => void;
}) {
  if (narrative.state !== "ready") {
    return (
      <div className="flex flex-col gap-2 text-sm">
        <p className="text-muted-foreground">{narrative.reason}</p>
        {narrative.state === "unavailable" ? (
          <Button size="sm" variant="outline" onClick={onRetry} className="self-start">
            Try again
          </Button>
        ) : null}
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-4 text-sm">
      {narrative.overview ? <p>{narrative.overview}</p> : null}
      {narrative.chapters.length === 0 ? (
        <p className="text-muted-foreground">
          The AI couldn&apos;t tie any explanation to specific events, so nothing is shown.
        </p>
      ) : (
        <ol className="flex flex-col gap-3">
          {narrative.chapters.map((c, i) => (
            <li key={i} className="border-l-2 border-amber-500/60 pl-3">
              <p className="text-muted-foreground text-xs">
                {short.format(new Date(c.started_at))}
                {c.ended_at.slice(0, 7) !== c.started_at.slice(0, 7)
                  ? ` to ${short.format(new Date(c.ended_at))}`
                  : ""}
              </p>
              <p className="font-medium">{c.title}</p>
              <p className="text-muted-foreground mt-0.5">{c.summary}</p>
              {c.why_it_matters ? (
                <p className="mt-1">
                  <span className="font-medium">Why it matters: </span>
                  {c.why_it_matters}
                </p>
              ) : null}
              <div className="mt-1.5 flex flex-wrap items-center gap-2 text-xs">
                <Badge tone="warning">Inferred · {c.confidence} confidence</Badge>
                <button
                  type="button"
                  onClick={() => onJump(c.event_ids)}
                  className="text-primary hover:underline"
                >
                  Show the {c.event_ids.length} cited event{c.event_ids.length === 1 ? "" : "s"}
                </button>
              </div>
            </li>
          ))}
        </ol>
      )}
      {narrative.links.length > 0 ? (
        <div>
          <p className="text-muted-foreground mb-1 text-xs font-medium">Connections</p>
          <ul className="flex flex-col gap-1.5 text-xs">
            {narrative.links.map((l, i) => (
              <li key={i}>
                <button
                  type="button"
                  onClick={() => onJump([l.from_event, l.to_event])}
                  className="text-left hover:underline"
                >
                  <span className="font-medium">
                    {byId.get(l.from_event)?.title ?? l.from_event}
                  </span>
                  <span className="text-muted-foreground"> {l.relation} </span>
                  <span className="font-medium">{byId.get(l.to_event)?.title ?? l.to_event}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      <p className="text-muted-foreground text-xs">
        Read {narrative.events_considered} events
        {narrative.rejected ? `; ${narrative.rejected} uncited statements were dropped` : ""}.
      </p>
    </div>
  );
}

function groupByMonth(events: TimelineEvent[]): [string, TimelineEvent[]][] {
  const groups: [string, TimelineEvent[]][] = [];
  for (const e of events) {
    const label = month.format(new Date(e.occurred_at));
    const last = groups.at(-1);
    if (last && last[0] === label) last[1].push(e);
    else groups.push([label, [e]]);
  }
  return groups;
}

/** The project's span as one line: chapters as bands above, every event as a tick. */
function ChapterAxis({
  events,
  narrative,
  current,
  onSelect,
  onChapter,
}: {
  events: TimelineEvent[]; // oldest first
  narrative: NarrativeView | null;
  current: string | null;
  onSelect: (id: string) => void;
  onChapter: (ids: string[]) => void;
}) {
  if (events.length < 2) return null;
  const start = new Date(events[0].occurred_at).getTime();
  const end = new Date(events.at(-1)!.occurred_at).getTime();
  const span = Math.max(end - start, 1);
  const at = (iso: string) => ((new Date(iso).getTime() - start) / span) * 100;
  const years: number[] = [];
  for (let y = new Date(start).getFullYear() + 1; y <= new Date(end).getFullYear(); y++)
    years.push(y);
  return (
    <div className="bg-card rounded-lg border px-4 pt-3 pb-2 shadow-xs">
      <div className="text-muted-foreground mb-2 flex items-center justify-between text-xs">
        <span>{short.format(new Date(start))}</span>
        <span className="font-medium">
          {narrative?.chapters.length
            ? `${narrative.chapters.length} chapters · ${events.length} events`
            : `${events.length} events`}
        </span>
        <span>{short.format(new Date(end))}</span>
      </div>
      <div className="relative h-7">
        {narrative?.chapters.map((c, i) => {
          const left = at(c.started_at);
          const width = Math.max(at(c.ended_at) - left, 1.5);
          return (
            <button
              key={i}
              type="button"
              title={`${c.title} (inferred)`}
              onClick={() => onChapter(c.event_ids)}
              className="bg-baton/25 hover:bg-baton/45 text-baton-foreground absolute top-0 h-6 truncate rounded px-1.5 text-left text-[11px] font-medium transition-colors dark:text-amber-100"
              style={{ left: `${left}%`, width: `${width}%`, minWidth: "1.5rem" }}
            >
              {c.title}
            </button>
          );
        })}
      </div>
      <div className="relative mt-1 h-6">
        <div className="bg-border absolute inset-x-0 top-1/2 h-px" />
        {years.map((y) => (
          <span
            key={y}
            className="text-muted-foreground absolute top-0 -translate-x-1/2 text-[10px]"
            style={{ left: `${at(new Date(y, 0, 1).toISOString())}%` }}
          >
            {y}
          </span>
        ))}
        {events.map((e) => (
          <button
            key={e.id}
            type="button"
            title={`${day.format(new Date(e.occurred_at))} · ${e.title}`}
            aria-label={e.title}
            onClick={() => onSelect(e.id)}
            className={cn(
              "absolute top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-[var(--card)] transition-transform hover:scale-150",
              CATEGORY[e.category].dot,
              e.significance === "high" ? "size-2.5" : "size-2",
              current === e.id && "ring-primary/60 scale-150",
            )}
            style={{ left: `${at(e.occurred_at)}%` }}
          />
        ))}
      </div>
    </div>
  );
}

function EventInspector({
  event: e,
  byId,
  chapters,
  onJump,
  onClose,
}: {
  event: TimelineEvent;
  byId: Map<string, TimelineEvent>;
  chapters: NarrativeView["chapters"];
  onJump: (ids: string[]) => void;
  onClose: () => void;
}) {
  return (
    <section
      aria-label="Event details"
      className="bg-card animate-in fade-in slide-in-from-right-2 flex flex-col gap-3 rounded-lg border p-4 shadow-xs duration-200"
    >
      <div className="flex items-start gap-2">
        <span
          aria-hidden
          className={cn("mt-1.5 size-2.5 shrink-0 rounded-full", CATEGORY[e.category].dot)}
        />
        <div className="min-w-0 flex-1">
          <p className="text-muted-foreground text-xs">
            {CATEGORY[e.category].label} · {e.source_system} ·{" "}
            {new Date(e.occurred_at).toLocaleDateString("en-GB", { dateStyle: "medium" })}
          </p>
          <h2 className="mt-0.5 text-sm font-semibold">{e.title}</h2>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close event details"
          className="text-muted-foreground hover:text-foreground rounded p-0.5"
        >
          <X aria-hidden className="size-4" />
        </button>
      </div>
      <p className="text-sm">{e.summary}</p>
      <dl className="grid grid-cols-[6rem_1fr] gap-x-3 gap-y-1.5 text-xs">
        <dt className="text-muted-foreground">Provenance</dt>
        <dd>
          <Badge tone="neutral">Fact</Badge> read from the {e.source_system} record
        </dd>
        <dt className="text-muted-foreground">Category</dt>
        <dd>{BASIS[e.category_basis]}</dd>
        {e.actor ? (
          <>
            <dt className="text-muted-foreground">By</dt>
            <dd>{e.actor}</dd>
          </>
        ) : null}
        <dt className="text-muted-foreground">Importance</dt>
        <dd className="capitalize">{e.significance}</dd>
      </dl>
      {e.linked_events.filter((id) => byId.has(id)).length ? (
        <div>
          <p className="text-muted-foreground mb-1 text-xs font-medium">Referenced in the record</p>
          <ul className="flex flex-col gap-1 text-xs">
            {e.linked_events
              .filter((id) => byId.has(id))
              .map((id) => (
                <li key={id}>
                  <button
                    type="button"
                    onClick={() => onJump([id])}
                    className="text-primary text-left hover:underline"
                  >
                    {byId.get(id)?.title}
                  </button>
                </li>
              ))}
          </ul>
        </div>
      ) : null}
      {chapters.length ? (
        <div>
          <p className="text-muted-foreground mb-1 text-xs font-medium">Part of (inferred)</p>
          <ul className="flex flex-col gap-1 text-xs">
            {chapters.map((c) => (
              <li key={c.title}>
                <button
                  type="button"
                  onClick={() => onJump(c.event_ids)}
                  className="text-left hover:underline"
                >
                  {c.title}
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {e.source_url ? (
        <a
          href={e.source_url}
          target="_blank"
          rel="noreferrer"
          className="text-primary inline-flex items-center gap-1 text-xs font-medium hover:underline"
        >
          Open in {e.source_system}
          <ExternalLink aria-hidden className="size-3" />
        </a>
      ) : null}
    </section>
  );
}

const ANSWER_MODE = {
  ai: { label: "From the history", tone: "neutral" },
  search: { label: "Search results, not an answer", tone: "warning" },
  not_found: { label: "Not in the history", tone: "muted" },
} as const;

function AskHistory({
  workspaceId,
  responsibilityId,
  byId,
  onJump,
}: {
  workspaceId: string;
  responsibilityId: string;
  byId: Map<string, TimelineEvent>;
  onJump: (ids: string[]) => void;
}) {
  const [question, setQuestion] = useState("");
  const [answers, setAnswers] = useState<HistoryAnswer[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();
  function submit(event: React.FormEvent) {
    event.preventDefault();
    const q = question.trim();
    if (q.length < 3) return;
    setError(null);
    startTransition(async () => {
      const result = await askHistoryAction(workspaceId, responsibilityId, q);
      if (result.error) setError(result.error);
      else if (result.answer) {
        setAnswers((a) => [result.answer!, ...a]);
        setQuestion("");
      }
    });
  }
  return (
    <section
      className="bg-card flex flex-col gap-3 rounded-lg border p-4 shadow-xs"
      aria-label="Ask about this history"
    >
      <div className="flex items-start gap-2">
        <MessageSquareText aria-hidden className="text-muted-foreground mt-0.5 size-4" />
        <div>
          <h2 className="text-sm font-semibold">Ask about this history</h2>
          <p className="text-muted-foreground text-xs">
            Answered only from the events on this page, with the events cited.
          </p>
        </div>
      </div>
      <form onSubmit={submit} className="flex gap-2">
        <label htmlFor="history-question" className="sr-only">
          Your question
        </label>
        <input
          id="history-question"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          maxLength={500}
          placeholder="e.g. Why was the canary added?"
          className={inputClass}
        />
        <Button
          type="submit"
          size="icon"
          aria-label="Ask"
          disabled={pending || question.trim().length < 3}
        >
          <SendHorizontal aria-hidden />
        </Button>
      </form>
      {pending ? (
        <p role="status" className="text-muted-foreground text-xs">
          Reading the history…
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="text-destructive text-xs">
          {error}
        </p>
      ) : null}
      {answers.map((a, i) => (
        <article
          key={i}
          className="animate-in fade-in flex flex-col gap-1.5 border-t pt-3 text-sm duration-300"
        >
          <p className="text-muted-foreground text-xs">{a.question}</p>
          <Badge tone={ANSWER_MODE[a.mode].tone} className="self-start">
            {ANSWER_MODE[a.mode].label}
          </Badge>
          <p>{a.answer}</p>
          {a.note ? <p className="text-muted-foreground text-xs">{a.note}</p> : null}
          {a.event_ids.length ? (
            <ul className="flex flex-wrap gap-1.5">
              {a.event_ids.map((id) => (
                <li key={id}>
                  <button
                    type="button"
                    onClick={() => onJump([id])}
                    className="bg-muted hover:bg-accent rounded px-1.5 py-0.5 text-left text-xs"
                  >
                    {byId.get(id)?.title ?? id}
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </article>
      ))}
    </section>
  );
}
