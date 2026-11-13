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
    <div className="border-line/15 bg-sunk/25 rounded-xl border p-5 text-left shadow-[inset_0_1px_0_rgba(255,255,255,0.12)] backdrop-blur-md">
      <p className="text-fg-soft text-sm font-medium">Production deployments · history</p>

      <ol className="border-line/10 mt-4 space-y-1 border-l">
        {MILESTONES.map((m) => (
          <li key={m.id}>
            <button
              type="button"
              onClick={() => setActiveId(m.id)}
              aria-pressed={activeId === m.id}
              className={cn(
                "-ml-px flex w-full items-baseline gap-4 border-l-2 py-2 pl-4 text-left transition-colors",
                activeId === m.id
                  ? "text-strong border-ac"
                  : "text-fg-mute hover:text-fg-soft border-transparent",
              )}
            >
              <span className="text-fg-mute w-24 shrink-0 text-xs tabular-nums">{m.date}</span>
              <span className="text-sm font-medium">{m.title}</span>
            </button>
          </li>
        ))}
      </ol>

      <div className="border-line/10 bg-sunk/30 mt-4 rounded-lg border p-4">
        <p className="text-fg-soft text-sm leading-relaxed">{active.summary}</p>
        <p className="text-fg-mute mt-4 text-xs font-medium">Sources</p>
        <ul className="mt-2 flex flex-wrap gap-2">
          {active.sources.map((s) => (
            <li
              key={s.ref}
              className="border-line/10 text-fg-soft rounded-md border px-2.5 py-1 text-xs"
            >
              <span className="text-fg-mute">{s.kind}</span> · {s.ref}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
