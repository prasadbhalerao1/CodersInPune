"use client";

import { Bot, Check, CircleSlash, Loader2, Square, TriangleAlert, Wrench } from "lucide-react";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

import { inputClass } from "@/components/action-form";
import { Button } from "@/components/ui/button";
import { readEvents } from "@/lib/sse";
import { cn } from "@/lib/utils";

type Step = {
  key: string;
  tool: string;
  label: string;
  status: "running" | "done" | "skipped" | "failed";
  summary: string;
  items: string[];
  calls: Record<string, number>;
};
type Done = {
  run_id: string;
  state: string;
  pending: number;
  proposals: { id: string; title: string; type: string; confidence: string }[];
};

const ICON = {
  running: <Loader2 aria-hidden className="text-primary size-4 animate-spin" />,
  done: <Check aria-hidden className="size-4 text-emerald-600 dark:text-emerald-400" />,
  skipped: <CircleSlash aria-hidden className="text-muted-foreground size-4" />,
  failed: <TriangleAlert aria-hidden className="size-4 text-amber-600" />,
};

/**
 * Handover Autopilot: runs the case's whole analysis in one go and shows every tool it uses
 * as it happens. It only proposes; the proposals below wait for a person to accept them.
 */
export function Autopilot({
  workspaceId,
  caseId,
  recipients,
}: {
  workspaceId: string;
  caseId: string;
  recipients: { user_id: string; name: string }[];
}) {
  const router = useRouter();
  const [steps, setSteps] = useState<Step[]>([]);
  const [done, setDone] = useState<Done | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [recipient, setRecipient] = useState("");
  const abort = useRef<AbortController | null>(null);

  async function run() {
    setSteps([]);
    setDone(null);
    setError(null);
    setRunning(true);
    abort.current = new AbortController();
    try {
      const response = await fetch(`/w/${workspaceId}/cases/${caseId}/autopilot`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(recipient ? { recipient_user_id: recipient } : {}),
        signal: abort.current.signal,
      });
      if (!response.ok || !response.body) {
        const problem = (await response.json().catch(() => ({}))) as { detail?: string };
        throw new Error(problem.detail ?? "Autopilot could not start.");
      }
      await readEvents(response, (name, data) => {
        if (name === "step") {
          const step = data as Step;
          setSteps((all) => {
            const at = all.findIndex((s) => s.key === step.key);
            return at < 0 ? [...all, step] : all.map((s, i) => (i === at ? step : s));
          });
        } else if (name === "done") setDone(data as Done);
        else if (name === "error") setError((data as { message: string }).message);
      });
      router.refresh();
    } catch (e) {
      if ((e as Error).name !== "AbortError") setError((e as Error).message);
    } finally {
      setRunning(false);
    }
  }

  return (
    <section
      aria-labelledby="autopilot"
      className="from-primary/[0.06] rounded-xl border bg-gradient-to-br to-transparent p-4"
    >
      <div className="flex flex-wrap items-center gap-3">
        <span className="bg-primary/10 text-primary flex size-9 items-center justify-center rounded-lg">
          <Bot aria-hidden className="size-5" />
        </span>
        <div className="min-w-0 flex-1">
          <h2 id="autopilot" className="font-semibold">
            Handover Autopilot
          </h2>
          <p className="text-muted-foreground text-sm">
            Reads the case, gathers the evidence, runs every reviewer and drafts the interview and
            brief. You watch each tool call; nothing changes until you accept a proposal.
          </p>
        </div>
        {running ? (
          <Button size="sm" variant="outline" onClick={() => abort.current?.abort()}>
            <Square aria-hidden className="size-3.5" /> Stop watching
          </Button>
        ) : (
          <div className="flex flex-wrap items-center gap-2">
            <select
              value={recipient}
              onChange={(e) => setRecipient(e.target.value)}
              aria-label="Brief recipient"
              className={cn(inputClass, "h-8 max-w-48 text-sm")}
            >
              <option value="">No brief yet</option>
              {recipients.map((m) => (
                <option key={m.user_id} value={m.user_id}>
                  Brief for {m.name}
                </option>
              ))}
            </select>
            <Button size="sm" onClick={run}>
              <Bot aria-hidden className="size-4" /> {steps.length ? "Run again" : "Run Autopilot"}
            </Button>
          </div>
        )}
      </div>

      {steps.length ? (
        <ol className="panel-in mt-4 flex flex-col gap-1.5" aria-live="polite">
          {steps.map((s) => (
            <li key={s.key} className="bg-card rounded-lg border px-3 py-2.5 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                {ICON[s.status]}
                <span className="font-medium">{s.label}</span>
                <code className="text-muted-foreground bg-muted rounded px-1.5 py-0.5 text-[11px]">
                  <Wrench aria-hidden className="mr-1 inline size-3" />
                  {s.tool}()
                </code>
                {Object.entries(s.calls).map(([tool, n]) => (
                  <code
                    key={tool}
                    className="text-primary bg-primary/10 rounded px-1.5 py-0.5 text-[11px]"
                  >
                    {tool} ×{n}
                  </code>
                ))}
                <span className="text-muted-foreground ml-auto text-xs">
                  {s.status === "running" ? "Working…" : s.summary}
                </span>
              </div>
              {s.items.length ? (
                <ul className="text-muted-foreground mt-1.5 flex flex-wrap gap-x-4 gap-y-0.5 pl-6 text-xs">
                  {s.items.map((i) => (
                    <li key={i} className="max-w-full truncate">
                      {i}
                    </li>
                  ))}
                </ul>
              ) : null}
            </li>
          ))}
        </ol>
      ) : null}

      {error ? (
        <p role="alert" className="mt-3 text-sm text-amber-700 dark:text-amber-300">
          {error}
        </p>
      ) : null}

      {done ? (
        <div className="panel-in bg-card mt-3 rounded-lg border p-3 text-sm">
          <p className="font-medium">
            {done.pending
              ? `${done.pending} proposal${done.pending === 1 ? "" : "s"} waiting for your review`
              : "No new proposals: the evidence holds no further gaps Autopilot could act on."}
          </p>
          {done.proposals.length ? (
            <ul className="text-muted-foreground mt-1.5 list-disc pl-5">
              {done.proposals.map((p) => (
                <li key={p.id}>{p.title}</li>
              ))}
            </ul>
          ) : null}
          <p className="text-muted-foreground mt-2 text-xs">
            Accept or reject each one under Proposals below.
          </p>
        </div>
      ) : null}
    </section>
  );
}
