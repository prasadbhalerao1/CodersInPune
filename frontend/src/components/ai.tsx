import { RunProgress } from "@/components/run-progress";
import { formatDateTime } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import type { ClaimKind, ClaimType, Confidence, EvidenceView, RunView } from "@/lib/types";
import { cn } from "@/lib/utils";

/** What a statement is. People must be able to tell facts from AI inferences at a glance. */
export function ClaimBadge({
  kind,
  type,
  supported = true,
}: {
  kind: ClaimKind;
  type: ClaimType;
  supported?: boolean;
}) {
  if (!supported) return <Badge tone="muted">Source withdrawn</Badge>;
  if (kind === "conflict") return <Badge tone="danger">Conflict</Badge>;
  if (kind === "missing") return <Badge tone="warning">Missing evidence</Badge>;
  if (type === "ai_inference")
    return (
      <Badge tone="muted" className="italic">
        AI inference
      </Badge>
    );
  if (type === "human_decision") return <Badge>Decision</Badge>;
  if (type === "rule") return <Badge>Rule</Badge>;
  return <Badge>Fact</Badge>;
}

const CONFIDENCE: Record<Confidence, string> = {
  high: "High confidence",
  medium: "Medium confidence",
  low: "Low confidence",
  insufficient: "Insufficient evidence",
};

export function ConfidenceNote({ value }: { value: Confidence }) {
  return (
    <span
      className={cn(
        "text-xs",
        value === "insufficient" ? "text-amber-700 dark:text-amber-300" : "text-muted-foreground",
      )}
    >
      {CONFIDENCE[value]}
    </span>
  );
}

const SOURCE: Record<EvidenceView["source_system"], string> = {
  relay: "Relay",
  github: "GitHub",
  linear: "Linear",
  notion: "Notion",
};

export function EvidenceList({ evidence }: { evidence: EvidenceView[] }) {
  if (evidence.length === 0) {
    return <p className="text-muted-foreground text-xs">No supporting evidence found.</p>;
  }
  return (
    <details className="group text-xs">
      <summary className="text-muted-foreground hover:text-foreground cursor-pointer select-none">
        {evidence.length} source{evidence.length === 1 ? "" : "s"}:{" "}
        {[...new Set(evidence.map((e) => SOURCE[e.source_system]))].join(", ")}
      </summary>
      <ul className="mt-2 flex flex-col gap-2 border-l pl-3">
        {evidence.map((e) => (
          <li key={e.id} className={cn(e.status !== "active" && "opacity-60")}>
            <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
              <span className="text-muted-foreground font-mono">{e.ref}</span>
              <span className="font-medium">
                {SOURCE[e.source_system]} · {e.source_type.replaceAll("_", " ")}
              </span>
              {e.url && e.status === "active" ? (
                <a
                  href={e.url}
                  target="_blank"
                  rel="noreferrer"
                  className="underline-offset-2 hover:underline"
                >
                  {e.title}
                </a>
              ) : (
                <span className={cn(e.status !== "active" && "line-through")}>{e.title}</span>
              )}
              {e.audience === "managers" ? <Badge tone="warning">Managers only</Badge> : null}
              {e.status !== "active" ? <Badge tone="muted">Withdrawn</Badge> : null}
            </p>
            <p className="text-muted-foreground">
              {e.source_ts ? formatDateTime(e.source_ts) : "Date unknown"}
              {e.revision ? ` · revision ${e.revision.slice(0, 24)}` : ""}
            </p>
            {e.excerpt ? <p className="mt-0.5 line-clamp-3">{e.excerpt}</p> : null}
          </li>
        ))}
      </ul>
    </details>
  );
}

const STATE: Record<
  RunView["state"],
  { label: string; tone: "danger" | "warning" | "neutral" | "muted" }
> = {
  queued: { label: "Queued", tone: "muted" },
  running: { label: "Running", tone: "neutral" },
  waiting_for_approval: { label: "Waiting for approval", tone: "warning" },
  completed: { label: "Completed", tone: "neutral" },
  partial: { label: "Partial", tone: "warning" },
  failed: { label: "AI failed", tone: "danger" },
  cancelled: { label: "Cancelled", tone: "muted" },
  timed_out: { label: "Timed out", tone: "danger" },
  needs_human_review: { label: "Needs human review", tone: "warning" },
};

const ERRORS: Record<string, string> = {
  quota_exhausted: "Every configured model key is out of quota. Try again later.",
  providers_unavailable: "No model provider answered.",
  provider_unavailable: "The model provider was unavailable.",
  provider_auth_failed: "A model key was rejected. Check the server's AI keys.",
  token_budget_exceeded: "The answer exceeded this step's token budget.",
  timeout: "The model took too long.",
  run_time_limit: "The run exceeded its time limit.",
  invalid_model_output: "The model's answer didn't match the expected format.",
};

export function RunStateBadge({ state }: { state: RunView["state"] }) {
  const s = STATE[state];
  return <Badge tone={s.tone}>{s.label}</Badge>;
}

export function explainRunError(code: string | null): string | null {
  if (!code) return null;
  return ERRORS[code] ?? code.replaceAll("_", " ");
}

export function RunSummary({ run }: { run: RunView }) {
  const active = run.state === "running" || run.state === "queued";
  if (active) {
    return (
      <RunProgress
        steps={run.steps}
        step={run.step}
        queued={run.state === "queued"}
        startedAt={run.created_at}
      />
    );
  }
  return (
    <div className="flex flex-col gap-1 text-sm">
      <p className="flex flex-wrap items-center gap-2">
        <RunStateBadge state={run.state} />
        <span className="text-muted-foreground text-xs">{formatDateTime(run.created_at)}</span>
      </p>
      <p className="text-muted-foreground text-xs tabular-nums">
        {run.ai === "not_configured"
          ? "Rules only: no AI model is configured on the server."
          : run.ai === "off"
            ? "Rules only: AI is switched off for this workspace."
            : `${run.provider ?? "model"}${run.model ? ` · ${run.model}` : ""}${
                run.key_index !== null ? ` · key ${run.key_index + 1}` : ""
              } · ${(run.input_tokens + run.output_tokens).toLocaleString()} tokens · ${(
                run.duration_ms / 1000
              ).toFixed(1)}s`}
      </p>
      {explainRunError(run.error_code) ? (
        <p className="text-xs text-red-700 dark:text-red-300">{explainRunError(run.error_code)}</p>
      ) : null}
    </div>
  );
}
