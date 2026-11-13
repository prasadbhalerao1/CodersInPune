"use client";

import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";

/** A miniature, animated run of the real workflow: change → discover → evidence → review →
 * capsule → acknowledge. Pauses on hover/focus; every step is clickable. */
const STEPS = [
  {
    key: "change",
    label: "A change happens",
    title: "Arjun Rao is leaving Platform",
    body: "Last day in two weeks. Relay opens a departure case and finds everything he owns.",
    rows: [
      ["Production deployments", "Critical", "Primary · no backup"],
      ["Platform on-call", "Critical", "Primary · backup Leo"],
    ],
  },
  {
    key: "evidence",
    label: "Evidence, not guesses",
    title: "Analysis from sources you authorised",
    body: "GitHub, Linear, Notion and Relay records. Every finding cites what it rests on.",
    rows: [
      ["Fact", "3 open PRs on deploy-pipelines", "GitHub · E4"],
      ["Missing", "No written rollback procedure", "Rule"],
      ["Conflict", "Two deploy runbooks disagree on canary", "E2 · E3"],
    ],
  },
  {
    key: "review",
    label: "People decide",
    title: "Proposals wait for a human",
    body: "Accept, edit or reject. AI never changes ownership, tasks or knowledge by itself.",
    rows: [
      ["Task", "Record the rollback procedure", "Accepted"],
      ["Knowledge", "Canary is mandatory (verified)", "Edited"],
      ["Task", "Rotate deploy keys", "Rejected · duplicate"],
    ],
  },
  {
    key: "handover",
    label: "A handover that fits",
    title: "Capsule for Dev Patel, approved",
    body: "Only what Dev may see. Restricted items are listed as omitted, never leaked.",
    rows: [
      ["Do first", "Pair on two canary deploys", "Cited · E4"],
      ["Watch out", "Old runbook skips the canary", "Conflict"],
      ["Omitted", "1 managers-only note", "Restricted"],
    ],
  },
  {
    key: "ack",
    label: "Ownership moves",
    title: "Acknowledged, then executed",
    body: "Dev acknowledges; ownership changes on the effective date with full history.",
    rows: [
      ["Acknowledged", "Dev Patel · v2", "Today"],
      ["Owner from 24 Nov", "Production deployments → Dev", "Scheduled"],
    ],
  },
] as const;

const TONE: Record<string, string> = {
  Critical: "text-red-700 dark:text-red-300",
  Fact: "text-foreground",
  Missing: "text-amber-700 dark:text-amber-300",
  Conflict: "text-amber-700 dark:text-amber-300",
  Accepted: "text-emerald-700 dark:text-emerald-300",
  Edited: "text-emerald-700 dark:text-emerald-300",
  "Rejected · duplicate": "text-muted-foreground",
  Restricted: "text-muted-foreground",
};

export function Walkthrough() {
  const [step, setStep] = useState(0);
  const [paused, setPaused] = useState(false);
  useEffect(() => {
    // Auto-advance is motion; people who ask for less of it step through by hand.
    if (paused || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const timer = setInterval(() => setStep((s) => (s + 1) % STEPS.length), 3600);
    return () => clearInterval(timer);
  }, [paused]);
  const current = STEPS[step];

  return (
    <div
      className="grid gap-6 lg:grid-cols-[18rem_minmax(0,1fr)]"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
    >
      <ol className="flex gap-2 overflow-x-auto lg:flex-col lg:gap-1" aria-label="Workflow steps">
        {STEPS.map((s, i) => (
          <li key={s.key}>
            <button
              type="button"
              onClick={() => setStep(i)}
              aria-current={i === step ? "step" : undefined}
              className={cn(
                "group flex w-full items-center gap-4 rounded-xl px-4 py-3 text-left whitespace-nowrap transition-colors",
                i === step ? "bg-line/[0.06]" : "hover:bg-line/[0.03]",
              )}
            >
              <span
                aria-hidden
                className={cn(
                  "font-bebas text-4xl leading-none tracking-wider transition-colors",
                  i === step
                    ? "text-ac"
                    : i < step
                      ? "text-fg-soft"
                      : "text-transparent [-webkit-text-stroke:1px_color-mix(in_srgb,var(--line)_35%,transparent)]",
                )}
              >
                {String(i + 1).padStart(2, "0")}
              </span>
              <span
                className={cn("text-sm", i === step ? "text-strong font-medium" : "text-fg-mute")}
              >
                {s.label}
              </span>
            </button>
          </li>
        ))}
      </ol>
      <div className="glass relative overflow-hidden">
        <div className="border-line/10 text-fg-mute border-b px-5 py-3 text-sm">Northwind Labs</div>
        <div
          key={current.key}
          className="animate-in fade-in slide-in-from-bottom-1 flex flex-col gap-4 p-5 duration-500"
        >
          <div>
            <p className="text-lg font-semibold tracking-tight">{current.title}</p>
            <p className="text-muted-foreground mt-1 text-sm">{current.body}</p>
          </div>
          <ul className="divide-y rounded-lg border text-sm">
            {current.rows.map(([a, b, c]) => (
              <li
                key={`${a}:${b}:${c}`}
                className="grid grid-cols-[7rem_minmax(0,1fr)_auto] items-center gap-3 px-3 py-2.5"
              >
                <span className={cn("font-medium", TONE[a] ?? "")}>{a}</span>
                <span className="truncate">{b}</span>
                <span className={cn("text-xs", TONE[c] ?? "text-muted-foreground")}>{c}</span>
              </li>
            ))}
          </ul>
          <div className="bg-muted h-1 overflow-hidden rounded-full" aria-hidden>
            <div
              className="bg-foreground h-1 rounded-full transition-[width] duration-500"
              style={{ width: `${((step + 1) / STEPS.length) * 100}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
