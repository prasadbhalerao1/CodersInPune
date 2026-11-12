"use client";

import React, { useState } from "react";
import { GitPullRequest, Bookmark, FileText, CheckCircle2 } from "lucide-react";

interface Milestone {
  id: string;
  tag: string;
  date: string;
  title: string;
  summary: string;
  citations: Array<{ source: string; ref: string }>;
}

const MILESTONES: Milestone[] = [
  {
    id: "m1",
    tag: "SYS.01",
    date: "14 Oct 2025",
    title: "PostgreSQL 17 Forced RLS Enforcement",
    summary:
      "Hardened tenant boundaries against bypass by superusers. Applied Row Level Security across 84 core tables with zero regression.",
    citations: [
      { source: "github", ref: "PR #388 (Merged)" },
      { source: "linear", ref: "SEC-104 (Done)" },
    ],
  },
  {
    id: "m2",
    tag: "SYS.02",
    date: "12 Dec 2025",
    title: "Stripe Webhook Idempotency Layer",
    summary:
      "Reconstructed webhook delivery retry mechanism using transactional outbox leases and database temporal GiST constraints.",
    citations: [
      { source: "github", ref: "PR #412 (Merged)" },
      { source: "notion", ref: "RFC: Payment Redundancy" },
    ],
  },
  {
    id: "m3",
    tag: "SYS.03",
    date: "28 Jan 2026",
    title: "Zero-Downtime Blue/Green Secrets Mesh",
    summary:
      "Automated secret rotation protocol without pod cycling. Documented failover runbook and escalation contact chains.",
    citations: [
      { source: "github", ref: "PR #495 (Merged)" },
      { source: "linear", ref: "OPS-220 (Closed)" },
      { source: "notion", ref: "SOP-Runbook v4" },
    ],
  },
];

export function MemoryReplayPreview() {
  const [activeId, setActiveId] = useState("m2");
  const active = MILESTONES.find((m) => m.id === activeId) || MILESTONES[1];

  return (
    <div className="rounded-xl border border-white/10 bg-[#0B0E16] p-4 text-left">
      {/* DAW-style Timeline Ribbon */}
      <div className="flex items-center justify-between border-b border-white/[0.08] pb-3">
        <span className="font-mono text-[9px] tracking-widest text-[#D2FF00] uppercase">
          PROJECT MEMORY REPLAY // CITED EVIDENCE SCRUBBER
        </span>
        <span className="font-mono text-[9px] text-zinc-500">100% CITED · 0% SPECULATION</span>
      </div>

      {/* Scrub Track */}
      <div className="mt-3 grid grid-cols-3 gap-2">
        {MILESTONES.map((m) => (
          <button
            key={m.id}
            type="button"
            onClick={() => setActiveId(m.id)}
            aria-pressed={activeId === m.id}
            className={`flex flex-col gap-1 rounded-lg border p-2 text-left transition-all ${
              activeId === m.id
                ? "border-[#D2FF00]/50 bg-[#141A28] shadow-[0_0_15px_rgba(210,255,0,0.1)]"
                : "border-white/5 bg-white/[0.02] text-zinc-400 hover:border-white/20"
            }`}
          >
            <div className="flex items-center justify-between font-mono text-[8px]">
              <span className={activeId === m.id ? "font-bold text-[#D2FF00]" : "text-zinc-500"}>
                {m.tag}
              </span>
              <span className="text-zinc-500">{m.date}</span>
            </div>
            <span className="truncate text-xs font-medium text-white">{m.title}</span>
          </button>
        ))}
      </div>

      {/* Active Synthesized Intelligence Card */}
      <div className="mt-3 rounded-lg border border-white/10 bg-black/40 p-3">
        <div className="flex items-start justify-between gap-2">
          <div>
            <span className="font-mono text-[10px] text-zinc-400">
              {active.date} · {active.tag}
            </span>
            <h4 className="text-sm font-semibold text-white">{active.title}</h4>
          </div>
          <span className="inline-flex items-center gap-1 rounded border border-emerald-500/30 bg-emerald-500/10 px-1.5 py-0.5 font-mono text-[9px] text-emerald-300">
            <CheckCircle2 className="h-3 w-3" /> VERIFIED
          </span>
        </div>

        <p className="mt-2 text-xs leading-relaxed text-zinc-300">{active.summary}</p>

        {/* Citations Proof Rail */}
        <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-white/[0.06] pt-2.5">
          <span className="font-mono text-[9px] tracking-wider text-zinc-500 uppercase">
            PROVEN SOURCES:
          </span>
          {active.citations.map((c, i) => (
            <span
              key={i}
              className="inline-flex items-center gap-1 rounded border border-white/10 bg-[#161C2A] px-2 py-0.5 font-mono text-[9px] text-zinc-200"
            >
              {c.source === "github" && <GitPullRequest className="h-2.5 w-2.5 text-purple-400" />}
              {c.source === "linear" && <Bookmark className="h-2.5 w-2.5 text-blue-400" />}
              {c.source === "notion" && <FileText className="h-2.5 w-2.5 text-emerald-400" />}
              <span>{c.ref}</span>
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
