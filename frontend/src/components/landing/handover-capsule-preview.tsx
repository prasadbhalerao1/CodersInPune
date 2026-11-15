  "use client";

import { useState } from "react";
import {
  ArrowRight,
  CheckCircle2,
  FileCheck,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import { cn } from "@/lib/utils";

type CapsuleTab = "ownership" | "gaps" | "risks" | "steps";
type CapsuleVersion = "v1" | "v2";

export function HandoverCapsulePreview() {
  const [tab, setTab] = useState<CapsuleTab>("ownership");
  const [version, setVersion] = useState<CapsuleVersion>("v2");
  const [acknowledged, setAcknowledged] = useState(false);
  const [activeQuestion, setActiveQuestion] = useState<string | null>(null);

  return (
    <div className="glass-dark overflow-clip rounded-2xl border border-line/15 text-left shadow-[0_24px_50px_rgba(0,0,0,0.85)]">
      {/* Module Header & Telemetry Bar */}
      <div className="border-b border-line/10 bg-line/[0.03] px-6 py-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <FileCheck className="size-4 text-ac" />
          <span className="font-mono text-[11px] font-semibold tracking-wider text-strong uppercase">
            Handover Capsule // Recipient: Dev Patel
          </span>
        </div>

        {/* Version Switcher */}
        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px] text-fg-mute uppercase">Version:</span>
          <div className="flex items-center gap-1 rounded-lg bg-sunk/60 p-0.5 border border-line/10">
            <button
              type="button"
              onClick={() => setVersion("v1")}
              className={cn(
                "rounded px-2 py-0.5 font-mono text-[10px] font-semibold transition-colors",
                version === "v1" ? "bg-line/15 text-strong" : "text-fg-mute hover:text-fg-soft",
              )}
            >
              v1 (AI draft)
            </button>
            <button
              type="button"
              onClick={() => setVersion("v2")}
              className={cn(
                "rounded px-2 py-0.5 font-mono text-[10px] font-semibold transition-colors",
                version === "v2" ? "bg-ac/20 text-ac" : "text-fg-mute hover:text-fg-soft",
              )}
            >
              v2 (VP Approved)
            </button>
          </div>
        </div>
      </div>

      {/* Brief Coverage Telemetry */}
      <div className="border-b border-line/10 px-6 py-4 bg-line/[0.015] flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="size-2 rounded-full bg-ac animate-ping" />
          <div>
            <span className="font-mono text-xs font-bold text-strong tracking-wide">
              Brief Coverage: 6 of 7 responsibilities cited (86% Grounded)
            </span>
            <p className="text-[11px] text-fg-mute">
              1 source changed since draft · Verified against GitHub, Linear & Notion
            </p>
          </div>
        </div>

        <span className="rounded-full border border-good/30 bg-good/10 px-2.5 py-0.5 font-mono text-[10px] font-semibold text-good uppercase">
          Zero Hallucination Gate Active
        </span>
      </div>

      {/* Capsule Navigation Tabs */}
      <div className="border-b border-line/10 px-6 py-2.5 flex items-center gap-2 overflow-x-auto">
        {[
          { id: "ownership", label: "What you now own" },
          { id: "gaps", label: "Knowledge gaps & questions" },
          { id: "risks", label: "Risks & conflicts" },
          { id: "steps", label: "Next steps" },
        ].map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id as CapsuleTab)}
            className={cn(
              "rounded-lg px-3 py-1.5 text-xs font-medium whitespace-nowrap transition-colors",
              tab === t.id
                ? "bg-line/15 text-strong font-semibold shadow-xs"
                : "text-fg-mute hover:text-fg-soft",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="p-6">
        {tab === "ownership" ? (
          <div className="space-y-3">
            <div className="rounded-xl border border-line/10 bg-line/[0.02] p-4">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="rounded bg-emerald-500/15 border border-emerald-500/30 px-2 py-0.5 font-mono text-[10px] font-bold text-emerald-400 uppercase">
                    Fact
                  </span>
                  <span className="font-syne font-bold text-strong text-sm">
                    Production deployments (Primary Owner)
                  </span>
                </div>
                <span className="font-mono text-[10px] text-fg-mute">Confidence: 0.98</span>
              </div>
              <p className="mt-2 text-xs text-fg-soft leading-relaxed">
                You inherit primary ownership of the release pipeline across payments-api and web-frontend. 3 active PRs pending merge on deploy-pipelines.
              </p>
              <div className="mt-3 flex items-center gap-2 font-mono text-[10px] text-fg-mute">
                <span className="text-ac">Evidence:</span>
                <span className="rounded bg-line/10 px-1.5 py-0.5 text-strong">
                  GitHub PR #142, PR #143
                </span>
                <span>·</span>
                <span className="rounded bg-line/10 px-1.5 py-0.5 text-strong">
                  CODEOWNERS: /deploy
                </span>
              </div>
            </div>

            <div className="rounded-xl border border-line/10 bg-line/[0.02] p-4">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="rounded bg-peri/15 border border-peri/30 px-2 py-0.5 font-mono text-[10px] font-bold text-peri uppercase">
                    Rule
                  </span>
                  <span className="font-syne font-bold text-strong text-sm">
                    Platform on-call (Primary)
                  </span>
                </div>
                <span className="font-mono text-[10px] text-fg-mute">Confidence: 0.92</span>
              </div>
              <p className="mt-2 text-xs text-fg-soft leading-relaxed">
                Rotation covers 24/7 Tier-1 alerts. Leo Martins is registered backup owner. Escalation contacts are verified in runbook v4.
              </p>
            </div>
          </div>
        ) : tab === "gaps" ? (
          <div className="space-y-3">
            <div className="rounded-xl border border-warn/30 bg-warn/[0.04] p-4">
              <div className="flex items-center gap-2">
                <ShieldAlert className="size-4 text-warn" />
                <span className="rounded bg-warn/20 px-1.5 py-0.5 font-mono text-[10px] font-bold text-warn uppercase">
                  Interview Question // Inferred Gap
                </span>
              </div>
              <p className="mt-2 text-xs text-strong font-medium leading-relaxed">
                &ldquo;Two runbooks disagree on canary deploy criteria. Runbook v2 says skip canaries for hotfixes, while RFC 18 mandates canaries unconditionally. Which is current?&rdquo;
              </p>
              <div className="mt-2.5 rounded bg-line/10 p-2 text-[11px] text-fg-soft">
                <span className="font-semibold text-strong">Arjun Rao (Outgoing):</span> &ldquo;RFC 18 superseded Runbook v2 after the Oct 14 checkout incident. Canaries are never skipped.&rdquo;
              </div>
            </div>
          </div>
        ) : tab === "risks" ? (
          <div className="space-y-3">
            <div className="rounded-xl border border-bad/30 bg-bad/[0.04] p-4">
              <div className="flex items-center gap-2">
                <span className="rounded bg-bad/20 px-1.5 py-0.5 font-mono text-[10px] font-bold text-bad uppercase">
                  Conflict
                </span>
                <span className="font-syne font-bold text-strong text-sm">
                  Conflicting rollback procedure detected
                </span>
              </div>
              <p className="mt-2 text-xs text-fg-soft leading-relaxed">
                {version === "v1"
                  ? "Unverified draft: Notion procedure requires manual DB rollback script."
                  : "Resolved in v2: Automated migration down-script in PR #412 confirmed by Engineering VP."}
              </p>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <ul className="divide-y divide-line/10 border border-line/10 rounded-xl bg-line/[0.02]">
              {[
                { title: "Pair on two canary deploys with Arjun", due: "Before 24 Nov", done: true },
                { title: "Acknowledge secrets rotation keys handover", due: "Today", done: false },
                { title: "Review escalated incident runbook v4", due: "26 Nov", done: false },
              ].map((s) => (
                <li key={s.title} className="flex items-center justify-between gap-3 p-3 text-xs">
                  <span className={cn(s.done ? "line-through text-fg-mute" : "text-strong font-medium")}>
                    {s.title}
                  </span>
                  <span className="font-mono text-[10px] text-fg-mute">{s.due}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Copilot Q&A within Capsule */}
      <div className="border-t border-line/10 bg-line/[0.02] p-6">
        <div className="flex items-center gap-2 mb-2.5">
          <Sparkles className="size-3.5 text-ac" />
          <span className="font-mono text-[11px] font-semibold tracking-wider text-strong uppercase">
            Ask Copilot About This Handover
          </span>
        </div>

        <div className="flex flex-wrap gap-2 mb-3">
          <button
            type="button"
            onClick={() => setActiveQuestion("deploy")}
            className={cn(
              "rounded-lg border px-3 py-1.5 text-xs text-left transition-colors",
              activeQuestion === "deploy"
                ? "border-ac bg-ac/15 text-strong font-medium"
                : "border-line/15 bg-line/[0.04] text-fg-soft hover:border-line/30",
            )}
          >
            &ldquo;How should I deploy payments-api?&rdquo;
          </button>
          <button
            type="button"
            onClick={() => setActiveQuestion("password")}
            className={cn(
              "rounded-lg border px-3 py-1.5 text-xs text-left transition-colors",
              activeQuestion === "password"
                ? "border-ac bg-ac/15 text-strong font-medium"
                : "border-line/15 bg-line/[0.04] text-fg-soft hover:border-line/30",
            )}
          >
            &ldquo;What is the AWS root password recovery process?&rdquo;
          </button>
        </div>

        {activeQuestion === "deploy" ? (
          <div className="rounded-xl border border-ac/30 bg-ac/[0.06] p-4 text-xs animate-in fade-in duration-300">
            <span className="font-mono text-[10px] font-bold text-ac uppercase block mb-1">
              Copilot Response // Grounded [E4, E2]
            </span>
            <p className="text-strong leading-relaxed">
              Deploy via the automated canary workflow in GitHub Actions. A 5-minute soak is mandatory [E2]. The obsolete hotfix skip procedure in old runbook v2 was formally deprecated [E4].
            </p>
          </div>
        ) : activeQuestion === "password" ? (
          <div className="rounded-xl border border-line/20 bg-line/[0.04] p-4 text-xs animate-in fade-in duration-300">
            <span className="font-mono text-[10px] font-bold text-fg-mute uppercase block mb-1">
              Zero Hallucination Guardrail // Not in evidence
            </span>
            <p className="text-fg-soft leading-relaxed">
              <strong className="text-strong">Not in the evidence.</strong> This handover capsule does not contain AWS root credentials or unverified recovery processes.
            </p>
          </div>
        ) : null}

        {/* Recipient Acknowledgement Button */}
        <div className="mt-5 pt-4 border-t border-line/10 flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs text-fg-mute">
            Recipient Dev Patel must acknowledge before ownership executes.
          </p>
          <button
            type="button"
            onClick={() => setAcknowledged(true)}
            disabled={acknowledged}
            className={cn(
              "inline-flex items-center gap-2 rounded-full px-5 py-2 font-mono text-xs font-bold tracking-wider uppercase transition-all",
              acknowledged
                ? "bg-good/20 text-good border border-good/40 cursor-default"
                : "bg-cta text-cta-fg hover:bg-cta-hover",
            )}
          >
            {acknowledged ? (
              <>
                <CheckCircle2 className="size-3.5" />
                Acknowledged by Dev Patel
              </>
            ) : (
              <>
                Acknowledge Receipt
                <ArrowRight className="size-3.5" />
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}