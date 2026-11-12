"use client";

import Link from "next/link";
import {
  AlertTriangle,
  ArrowRight,
  FileCheck2,
  Flame,
  Lock,
  ShieldCheck,
  UserCheck,
} from "lucide-react";
import { useState } from "react";

type DurationOption = "3d" | "7d" | "14d" | "30d";

// Sample readiness scores for the demo scenario (no backend involved): the score for the
// absence window as-is, and after Dev Patel is simulated as interim cover.
const SCENARIO: Record<
  DurationOption,
  { label: string; days: number; uncovered: number; covered: number }
> = {
  "3d": { label: "Short Leave (3 Days)", days: 3, uncovered: 92, covered: 98 },
  "7d": { label: "One-Week Sabbatical", days: 7, uncovered: 74, covered: 94 },
  "14d": { label: "14 Days Notice Period", days: 14, uncovered: 55, covered: 88 },
  "30d": { label: "Unplanned Departure (30 Days)", days: 30, uncovered: 32, covered: 82 },
};

const DURATIONS: DurationOption[] = ["3d", "7d", "14d", "30d"];

function statusColor(score: number) {
  if (score >= 85) return "#00F5A0"; // Emerald
  if (score >= 70) return "#F59E0B"; // Baton Amber
  return "#FF334B"; // Crimson
}

export function HeroSandbox() {
  const [duration, setDuration] = useState<DurationOption>("14d");
  const [simulatedCover, setSimulatedCover] = useState(false);

  const scenario = SCENARIO[duration];
  const score = simulatedCover ? scenario.covered : scenario.uncovered;
  const coverGain = scenario.covered - scenario.uncovered;
  const color = statusColor(score);
  const critical = score < 70;
  const strokeDashoffset = 283 - (283 * score) / 100;

  const insight = simulatedCover
    ? "Dev Patel assigned as interim steward. Single point of failure resolved, but workload balance requires observation."
    : scenario.days >= 14
      ? "0 active backups for Production Deployments. A deployment outage during this window cannot be escalated."
      : "Mild coverage buffer in place. Routine maintenance proceeds with minor delay.";

  return (
    <div className="relative w-full overflow-hidden rounded-3xl border border-white/20 bg-gradient-to-b from-[#141926]/95 via-[#0C1018]/98 to-[#06070B] p-6 shadow-[0_32px_80px_rgba(0,0,0,0.85),inset_0_1px_0_rgba(255,255,255,0.2)] backdrop-blur-2xl">
      {/* Top Instrumentation Telemetry Header */}
      <div className="flex items-center justify-between border-b border-white/[0.08] pb-3 text-xs">
        <div className="flex items-center gap-2.5">
          <span className="jewel-crimson" />
          <span className="font-mono text-[10px] font-semibold tracking-widest text-zinc-300 uppercase">
            SOVEREIGN CONTINUITY INSTRUMENT // SYS.01
          </span>
        </div>
        <div className="flex items-center gap-1.5 rounded-full border border-emerald-500/25 bg-emerald-500/10 px-2.5 py-0.5 font-mono text-[9px] tracking-wider text-emerald-400">
          <Lock className="h-2.5 w-2.5" aria-hidden />
          <span>KERNEL RLS PROTECTED</span>
        </div>
      </div>

      {/* Target Key Person Departure Card */}
      <div className="mt-4 flex flex-col justify-between gap-3 rounded-2xl border border-white/10 bg-white/[0.03] p-4 shadow-inner sm:flex-row sm:items-center">
        <div className="flex items-center gap-3.5">
          <div className="relative flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-white/20 bg-zinc-900 text-sm font-extrabold text-white shadow-[inset_0_1px_1px_rgba(255,255,255,0.4)]">
            AR
            <span className="absolute -right-1 -bottom-1 h-3.5 w-3.5 rounded-full border-2 border-[#0C1018] bg-[#FF334B] shadow-[0_0_8px_#FF334B]" />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="truncate text-sm font-bold tracking-tight text-white">
                Arjun Rao
              </span>
              <span className="rounded border border-rose-800/50 bg-rose-950/90 px-2 py-0.5 font-mono text-[9px] font-semibold tracking-wider text-rose-300 uppercase">
                ABSENT FOR {scenario.days} DAYS
              </span>
            </div>
            <p className="mt-0.5 truncate text-xs text-zinc-400">
              Primary Owner: Production Deployments &amp; Secrets Mesh
            </p>
          </div>
        </div>

        <div className="flex items-center justify-between border-t border-white/[0.06] pt-2 sm:flex-col sm:items-end sm:border-t-0 sm:pt-0">
          <span className="font-mono text-[9px] tracking-widest text-zinc-500 uppercase">
            ACTIVE BACKUPS
          </span>
          <span
            className={`font-mono text-xs font-black ${simulatedCover ? "text-emerald-400" : "text-rose-400"}`}
          >
            {simulatedCover ? "1 ASSIGNED" : "0 ASSIGNED"}
          </span>
        </div>
      </div>

      {/* Tactile Absence Duration Selector */}
      <div className="mt-5">
        <div className="flex items-center justify-between">
          <span
            id="absence-window-label"
            className="font-mono text-[10px] font-semibold tracking-wider text-zinc-400 uppercase"
          >
            SIMULATE ABSENCE WINDOW
          </span>
          <span className="font-mono text-[10px] font-medium text-[#D2FF00]">{scenario.label}</span>
        </div>

        <div
          role="group"
          aria-labelledby="absence-window-label"
          className="mt-2 grid grid-cols-4 gap-2 rounded-xl border border-white/[0.08] bg-black/50 p-1.5 shadow-inner"
        >
          {DURATIONS.map((d) => (
            <button
              key={d}
              type="button"
              onClick={() => setDuration(d)}
              aria-pressed={duration === d}
              className={`rounded-lg py-2 text-center font-mono text-xs font-bold transition-all ${
                duration === d
                  ? "border border-white/20 bg-[#1E273A] text-[#D2FF00] shadow-[inset_0_1px_0_rgba(255,255,255,0.25),0_4px_12px_rgba(0,0,0,0.6)]"
                  : "text-zinc-400 hover:text-white"
              }`}
            >
              {d.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {/* Real-Time Readiness Dial & Blast Radius Telemetry */}
      <div
        aria-live="polite"
        className="mt-5 grid grid-cols-[auto_1fr] items-center gap-4.5 rounded-2xl border border-white/10 bg-black/40 p-4 shadow-lg"
      >
        {/* SVG Circular Readiness Gauge */}
        <div className="relative flex h-20 w-20 shrink-0 items-center justify-center">
          <svg className="h-full w-full -rotate-90" viewBox="0 0 100 100" aria-hidden>
            {/* Background Track */}
            <circle
              cx="50"
              cy="50"
              r="44"
              fill="none"
              stroke="rgba(255,255,255,0.06)"
              strokeWidth="8"
            />
            {/* Active Telemetry Arc */}
            <circle
              cx="50"
              cy="50"
              r="44"
              fill="none"
              stroke={color}
              strokeWidth="8"
              strokeDasharray="283"
              strokeDashoffset={strokeDashoffset}
              strokeLinecap="round"
              className="transition-all duration-500 ease-out"
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
            <span className="font-mono text-2xl leading-none font-black text-white">{score}</span>
            <span className="mt-0.5 font-mono text-[8px] tracking-widest text-zinc-500 uppercase">
              / 100
            </span>
          </div>
        </div>

        {/* Dynamic Telemetry Insight */}
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            {critical ? (
              <Flame className="h-4 w-4 shrink-0 text-rose-500" aria-hidden />
            ) : (
              <ShieldCheck className="h-4 w-4 shrink-0 text-emerald-400" aria-hidden />
            )}
            <span className="font-mono text-xs font-bold tracking-tight" style={{ color }}>
              {critical ? "CRITICAL CONTINUITY VULNERABILITY" : "RESILIENT PROTOCOL READY"}
            </span>
          </div>
          <p className="mt-1 text-xs leading-relaxed text-zinc-300">{insight}</p>
        </div>
      </div>

      {/* Successor Simulation Action */}
      <div className="mt-5 flex flex-col gap-2.5">
        <button
          type="button"
          onClick={() => setSimulatedCover((v) => !v)}
          aria-pressed={simulatedCover}
          className={`flex w-full items-center justify-between rounded-xl border p-3 text-xs font-semibold transition-all ${
            simulatedCover
              ? "border-[#00F5A0]/40 bg-[#00F5A0]/10 text-[#00F5A0] shadow-[0_0_20px_rgba(0,245,160,0.2)]"
              : "border-white/10 bg-white/[0.04] text-zinc-300 hover:border-[#F59E0B]/40 hover:text-white"
          }`}
        >
          <span className="flex items-center gap-2">
            <UserCheck className="h-4 w-4 text-[#F59E0B]" aria-hidden />
            <span>
              {simulatedCover ? "REVERT COVER SIMULATION" : "SIMULATE SUCCESSOR: DEV PATEL"}
            </span>
          </span>
          <span className="font-mono text-[10px] font-bold uppercase">
            {simulatedCover ? `ACTIVE (${score}/100)` : `+${coverGain} PTS`}
          </span>
        </button>

        {simulatedCover && (
          <div className="flex flex-col gap-2">
            {/* Algorithmic Workload Warning */}
            <div className="flex items-center gap-2 rounded-lg border border-amber-500/25 bg-amber-500/10 px-3 py-2 text-[11px] text-amber-300">
              <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-amber-400" aria-hidden />
              <span>
                ALGORITHMIC ADVISORY: Dev carries 2.4x baseline team load. Handover capsule
                recommended.
              </span>
            </div>

            {/* Cryptographic Handover Capsule Preview Badge */}
            <div className="rounded-xl border border-emerald-500/20 bg-emerald-950/20 p-3 text-xs">
              <div className="flex items-center justify-between font-mono text-[10px] font-bold text-emerald-400 uppercase">
                <span className="flex items-center gap-1.5">
                  <FileCheck2 className="h-3.5 w-3.5" aria-hidden />
                  <span>[E3] AUDITED HANDOVER DOSSIER READY</span>
                </span>
                <span className="rounded bg-emerald-500/20 px-1.5 py-0.5 text-emerald-300">
                  SOD VERIFIED
                </span>
              </div>
              <div className="mt-2 flex flex-wrap gap-2 font-mono text-[9px] text-zinc-300">
                <span className="rounded border border-white/10 bg-black/40 px-2 py-0.5">
                  OUTGOING: ARJUN RAO
                </span>
                <span className="rounded border border-white/10 bg-black/40 px-2 py-0.5">
                  INCOMING: DEV PATEL
                </span>
                <span className="rounded border border-white/10 bg-black/40 px-2 py-0.5">
                  SEAL: DUAL-KEY
                </span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* High-Status Boardroom Action */}
      <div className="mt-5 border-t border-white/[0.08] pt-4">
        <Link href="/workspaces" className="luxury-btn group !h-12 w-full !text-xs">
          <span className="jewel-emerald" />
          <span>TAKE COMMAND // EXECUTE THE TRANSFER</span>
          <ArrowRight
            className="h-3.5 w-3.5 transition-transform group-hover:translate-x-1"
            aria-hidden
          />
        </Link>
        <span className="mt-2.5 block text-center font-mono text-[9px] tracking-wider text-zinc-500">
          STRICT TENANT RLS · NO HALLUCINATIONS · FULLY CITED EVIDENCE
        </span>
      </div>
    </div>
  );
}
