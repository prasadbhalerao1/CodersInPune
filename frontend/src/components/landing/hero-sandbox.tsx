"use client";

import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { useState } from "react";

import { cn } from "@/lib/utils";

// Sample scenario (no backend): Arjun Rao is leaving; three responsibilities depend on him.
// The model mirrors the product's idea: readiness rises with the share of weighted work
// a cover candidate can take, and drops when that candidate is already overloaded.

const WINDOWS = [
  { id: "3d", label: "3 days", base: 92 },
  { id: "7d", label: "1 week", base: 74 },
  { id: "14d", label: "2 weeks", base: 55 },
  { id: "30d", label: "30 days", base: 32 },
] as const;

const WORK = [
  {
    id: "deploy",
    name: "Production deployments",
    level: "Critical",
    weight: 22,
    note: "Release train, 2 Dec",
  },
  {
    id: "secrets",
    name: "Secrets rotation",
    level: "Critical",
    weight: 14,
    note: "Quarterly rotation, 9 Dec",
  },
  { id: "notes", name: "Release notes", level: "Routine", weight: 4, note: "Weekly" },
] as const;

const CANDIDATES = [
  {
    id: "dev",
    name: "Dev Patel",
    team: "Platform",
    covers: ["deploy", "secrets"],
    load: "Carrying 2.4x the usual load",
    overloaded: true,
  },
  {
    id: "leo",
    name: "Leo Martins",
    team: "Platform",
    covers: ["deploy"],
    load: "Usual load",
    overloaded: false,
  },
  {
    id: "sam",
    name: "Sam Okafor",
    team: "Support",
    covers: ["notes"],
    load: "Usual load",
    overloaded: false,
  },
] as const;

const TOTAL_WEIGHT = WORK.reduce((n, w) => n + w.weight, 0);
const OVERLOAD_PENALTY = 8;

function readiness(base: number, coverId: string | null) {
  const cand = CANDIDATES.find((c) => c.id === coverId);
  if (!cand) return base;
  const covered = WORK.filter((w) => (cand.covers as readonly string[]).includes(w.id)).reduce(
    (n, w) => n + w.weight,
    0,
  );
  const score =
    base + ((100 - base) * covered) / TOTAL_WEIGHT - (cand.overloaded ? OVERLOAD_PENALTY : 0);
  return Math.max(0, Math.min(100, Math.round(score)));
}

function verdict(score: number) {
  if (score >= 85) return { word: "Ready", color: "#00F5A0" };
  if (score >= 70) return { word: "Fragile", color: "#F59E0B" };
  return { word: "At risk", color: "#FF5468" };
}

export function HeroSandbox() {
  const [windowId, setWindowId] = useState<(typeof WINDOWS)[number]["id"]>("14d");
  const [coverId, setCoverId] = useState<string | null>(null);

  const win = WINDOWS.find((w) => w.id === windowId)!;
  const cand = CANDIDATES.find((c) => c.id === coverId) ?? null;
  const score = readiness(win.base, coverId);
  const v = verdict(score);
  const uncovered = WORK.filter((w) => !cand || !(cand.covers as readonly string[]).includes(w.id));
  const uncoveredCritical = uncovered.filter((w) => w.level === "Critical");

  let summary: string;
  if (!cand) {
    summary = `${uncoveredCritical.length} critical responsibilities have no backup. If something breaks in these ${win.label}, nobody is cleared to take it.`;
  } else if (uncovered.length === 0) {
    summary = `${cand.name} can take everything Arjun owns.`;
  } else {
    summary = `${cand.name} takes ${WORK.length - uncovered.length} of ${WORK.length}. Still uncovered: ${uncovered.map((u) => u.name.toLowerCase()).join(", ")}.`;
  }

  return (
    <div className="glass-dark overflow-hidden">
      {/* Who */}
      <div className="flex items-center gap-4 border-b border-white/10 px-6 py-5">
        <span className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-zinc-800 text-sm font-semibold text-zinc-200">
          AR
        </span>
        <div className="min-w-0">
          <p className="font-semibold text-[#F1EDE6]">Arjun Rao</p>
          <p className="text-sm text-zinc-400">Platform engineer, away for {win.label}</p>
        </div>
      </div>

      {/* How long */}
      <div className="border-b border-white/10 px-6 py-5">
        <p id="away-label" className="text-sm font-medium text-zinc-300">
          How long is he away?
        </p>
        <div
          role="group"
          aria-labelledby="away-label"
          className="mt-3 grid grid-cols-4 gap-1 rounded-lg bg-black/40 p-1"
        >
          {WINDOWS.map((w) => (
            <button
              key={w.id}
              type="button"
              aria-pressed={windowId === w.id}
              onClick={() => setWindowId(w.id)}
              className={cn(
                "rounded-md py-2 text-sm transition-colors",
                windowId === w.id
                  ? "bg-white/10 font-medium text-white"
                  : "text-zinc-400 hover:text-zinc-200",
              )}
            >
              {w.label}
            </button>
          ))}
        </div>
      </div>

      {/* Result */}
      <div aria-live="polite" className="border-b border-white/10 px-6 py-5">
        <div className="flex items-end justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-zinc-300">Readiness</p>
            <p className="mt-1 flex items-baseline gap-2">
              <span className="font-bebas text-6xl leading-none text-white tabular-nums">
                {score}
              </span>
              <span className="text-lg font-medium" style={{ color: v.color }}>
                {v.word}
              </span>
            </p>
          </div>
          <p className="max-w-[16rem] text-right text-sm leading-snug text-zinc-400">{summary}</p>
        </div>
        <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-white/10">
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{ width: `${score}%`, background: v.color }}
          />
        </div>
        {cand?.overloaded ? (
          <p className="mt-3 text-sm text-amber-400">
            {cand.name} is already overloaded, so readiness drops by {OVERLOAD_PENALTY} points.
          </p>
        ) : null}
      </div>

      {/* What is affected */}
      <div className="border-b border-white/10 px-6 py-5">
        <p className="text-sm font-medium text-zinc-300">What depends on him</p>
        <ul className="mt-3 divide-y divide-white/[0.07]">
          {WORK.map((w) => {
            const covered = cand ? (cand.covers as readonly string[]).includes(w.id) : false;
            return (
              <li key={w.id} className="flex items-center justify-between gap-4 py-2.5 text-sm">
                <div className="min-w-0">
                  <p className="text-zinc-100">{w.name}</p>
                  <p className="text-xs text-zinc-500">
                    {w.level} · {w.note}
                  </p>
                </div>
                <span
                  className={cn(
                    "shrink-0 text-xs font-medium",
                    covered
                      ? "text-emerald-400"
                      : w.level === "Critical"
                        ? "text-rose-400"
                        : "text-zinc-500",
                  )}
                >
                  {covered ? `Covered by ${cand!.name.split(" ")[0]}` : "No backup"}
                </span>
              </li>
            );
          })}
        </ul>
      </div>

      {/* Who could cover */}
      <div className="px-6 py-5">
        <p className="text-sm font-medium text-zinc-300">Who could cover? Try one.</p>
        <ul className="mt-3 space-y-2">
          {CANDIDATES.map((c) => {
            const selected = coverId === c.id;
            return (
              <li key={c.id}>
                <button
                  type="button"
                  aria-pressed={selected}
                  onClick={() => setCoverId(selected ? null : c.id)}
                  className={cn(
                    "flex w-full items-center justify-between gap-4 rounded-lg border px-4 py-3 text-left transition-colors",
                    selected
                      ? "border-[#C4FF00]/60 bg-[#C4FF00]/[0.06]"
                      : "border-white/10 hover:border-white/25",
                  )}
                >
                  <span>
                    <span className="block text-sm font-medium text-zinc-100">{c.name}</span>
                    <span className="block text-xs text-zinc-500">
                      {c.team} · {c.load}
                    </span>
                  </span>
                  <span className="shrink-0 text-sm text-zinc-300 tabular-nums">
                    {readiness(win.base, c.id)}
                    <span className="text-xs text-zinc-500"> / 100</span>
                  </span>
                </button>
              </li>
            );
          })}
        </ul>

        <Link
          href="/workspaces"
          className="group mt-5 inline-flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-[#F1EDE6] text-sm font-semibold text-[#090D18] transition-colors hover:bg-white"
        >
          Plan a real handover
          <ArrowRight
            className="h-4 w-4 transition-transform group-hover:translate-x-0.5"
            aria-hidden
          />
        </Link>
        <p className="mt-3 text-center text-xs text-zinc-500">
          Sample data. In Relay a simulation is read-only and never changes ownership.
        </p>
      </div>
    </div>
  );
}
