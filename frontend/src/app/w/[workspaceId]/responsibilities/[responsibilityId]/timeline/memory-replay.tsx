"use client";

import {
  BookOpenText,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  Link2,
  Pause,
  Play,
  RotateCcw,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState, useTransition } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { NarrativeView, TimelineCategory, TimelineEvent, TimelineView } from "@/lib/types";
import { cn } from "@/lib/utils";

import { narrateTimelineAction } from "./actions";

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
}: {
  workspaceId: string;
  timeline: TimelineView;
}) {
  const [filter, setFilter] = useState<TimelineCategory | null>(null);
  const [cursor, setCursor] = useState<number | null>(null); // replay position, oldest = 0
  const [playing, setPlaying] = useState(false);
  const [focus, setFocus] = useState<Set<string>>(new Set());
  const [narrative, setNarrative] = useState<NarrativeView | null>(null);
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

        {groups.length === 0 ? (
          <p className="text-muted-foreground px-1 text-sm">No events in this view.</p>
        ) : (
          groups.map(([label, events]) => (
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
                    register={(el) => {
                      if (el) rows.current.set(e.id, el);
                      else rows.current.delete(e.id);
                    }}
                  />
                ))}
              </ol>
            </section>
          ))
        )}
        {timeline.truncated ? (
          <p className="text-muted-foreground text-xs">
            Showing the most recent {timeline.events.length} of {timeline.total} events.
          </p>
        ) : null}
      </div>

      <aside className="flex flex-col gap-4 xl:sticky xl:top-20 xl:max-h-[calc(100dvh-6rem)] xl:self-start xl:overflow-y-auto">
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
            <Narrative narrative={narrative} byId={byId} onJump={jump} onRetry={explain} />
          )}
          {error ? (
            <p role="alert" className="text-destructive text-sm">
              {error}
            </p>
          ) : null}
        </div>

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
  register,
}: {
  event: TimelineEvent;
  byId: Map<string, TimelineEvent>;
  current: boolean;
  focused: boolean;
  onJump: (ids: string[]) => void;
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
