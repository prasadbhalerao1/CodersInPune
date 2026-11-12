"use client";

import { useState } from "react";

import { cn } from "@/lib/utils";

interface Milestone {
  id: string;
  date: string;
  title: string;
  summary: string;
  sources: Array<{ kind: "GitHub" | "Linear" | "Notion"; ref: string }>;
}

const MILESTONES: Milestone[] = [
  {
    id: "m1",
    date: "14 Oct 2025",
    title: "Forced row-level security on every tenant table",
    summary:
      "Tenant boundaries hardened so even application bugs cannot cross them. Applied across the schema with no regressions.",
    sources: [
      { kind: "GitHub", ref: "PR #388, merged" },
      { kind: "Linear", ref: "SEC-104, done" },
    ],
  },
  {
    id: "m2",
    date: "12 Dec 2025",
    title: "Idempotent webhook delivery",
    summary:
      "Retry logic rebuilt around transactional outbox leases and database constraints so a replayed webhook is harmless.",
    sources: [
      { kind: "GitHub", ref: "PR #412, merged" },
      { kind: "Notion", ref: "RFC: Payment redundancy" },
    ],
  },
  {
    id: "m3",
    date: "28 Jan 2026",
    title: "Zero-downtime secrets rotation",
    summary:
      "Secrets rotate without cycling pods. The failover runbook and escalation contacts were written down alongside it.",
    sources: [
      { kind: "GitHub", ref: "PR #495, merged" },
      { kind: "Linear", ref: "OPS-220, closed" },
      { kind: "Notion", ref: "Runbook v4" },
    ],
  },
];

export function MemoryReplayPreview() {
  const [activeId, setActiveId] = useState("m2");
  const active = MILESTONES.find((m) => m.id === activeId) ?? MILESTONES[1];

  return (
    <div className="rounded-xl border border-white/15 bg-black/25 p-5 text-left shadow-[inset_0_1px_0_rgba(255,255,255,0.12)] backdrop-blur-md">
      <p className="text-sm font-medium text-zinc-300">Production deployments · history</p>

      <ol className="mt-4 space-y-1 border-l border-white/10">
        {MILESTONES.map((m) => (
          <li key={m.id}>
            <button
              type="button"
              onClick={() => setActiveId(m.id)}
              aria-pressed={activeId === m.id}
              className={cn(
                "-ml-px flex w-full items-baseline gap-4 border-l-2 py-2 pl-4 text-left transition-colors",
                activeId === m.id
                  ? "border-[#C4FF00] text-white"
                  : "border-transparent text-zinc-400 hover:text-zinc-200",
              )}
            >
              <span className="w-24 shrink-0 text-xs text-zinc-500 tabular-nums">{m.date}</span>
              <span className="text-sm font-medium">{m.title}</span>
            </button>
          </li>
        ))}
      </ol>

      <div className="mt-4 rounded-lg border border-white/10 bg-black/30 p-4">
        <p className="text-sm leading-relaxed text-zinc-200">{active.summary}</p>
        <p className="mt-4 text-xs font-medium text-zinc-500">Sources</p>
        <ul className="mt-2 flex flex-wrap gap-2">
          {active.sources.map((s) => (
            <li
              key={s.ref}
              className="rounded-md border border-white/10 px-2.5 py-1 text-xs text-zinc-300"
            >
              <span className="text-zinc-500">{s.kind}</span> · {s.ref}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
