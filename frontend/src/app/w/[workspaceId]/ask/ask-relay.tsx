"use client";

import { ArrowUpRight, SendHorizontal, Sparkles, Square } from "lucide-react";
import Link from "next/link";
import { useRef, useState, type FormEvent } from "react";

import { inputClass } from "@/components/action-form";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { hitPath } from "@/lib/search";
import { readEvents } from "@/lib/sse";
import type { SearchHit } from "@/lib/types";
import { cn } from "@/lib/utils";

type Source = {
  ref: string;
  kind: SearchHit["kind"];
  id: string;
  title: string;
  detail: string | null;
  url: string | null;
};
type Final = {
  mode: "ai" | "search" | "not_found";
  answer: string;
  cited: string[];
  note: string | null;
};
type Turn = {
  question: string;
  sources: Source[];
  draft: string;
  final: Final | null;
  error?: string;
};

const SUGGESTIONS = [
  "Who is the backup for payments on-call?",
  "What did we decide about webhooks?",
  "Which responsibilities have no second owner?",
  "How do we rotate the webhook secret?",
];

const KIND_LABEL: Partial<Record<SearchHit["kind"], string>> = {
  responsibility: "Responsibility",
  knowledge: "Knowledge",
  case: "Case",
  person: "Person",
  team: "Team",
  asset: "Asset",
  risk: "Risk",
  github: "GitHub",
  linear: "Linear",
};

/** Workspace-wide questions, answered as they are written, every claim a clickable source. */
export function AskRelay({ workspaceId }: { workspaceId: string }) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const abort = useRef<AbortController | null>(null);

  const update = (fn: (t: Turn) => Turn) =>
    setTurns((all) => all.map((t, i) => (i === all.length - 1 ? fn(t) : t)));

  async function ask(text: string, e?: FormEvent) {
    e?.preventDefault();
    const q = text.trim();
    if (q.length < 3 || busy) return;
    setQuestion("");
    setBusy(true);
    setTurns((all) => [...all, { question: q, sources: [], draft: "", final: null }]);
    abort.current = new AbortController();
    try {
      const response = await fetch(`/w/${workspaceId}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
        signal: abort.current.signal,
      });
      if (!response.ok || !response.body) {
        const problem = (await response.json().catch(() => ({}))) as { detail?: string };
        throw new Error(problem.detail ?? "The question could not be sent.");
      }
      await readEvents(response, (name, data) => {
        if (name === "sources")
          update((t) => ({ ...t, sources: (data as { sources: Source[] }).sources }));
        else if (name === "delta")
          update((t) => ({ ...t, draft: t.draft + (data as { text: string }).text }));
        else if (name === "final") update((t) => ({ ...t, final: data as Final }));
        else if (name === "error")
          update((t) => ({ ...t, error: (data as { message: string }).message }));
      });
    } catch (err) {
      const stopped = (err as Error).name === "AbortError";
      update((t) => ({ ...t, error: stopped ? "Stopped." : (err as Error).message }));
    } finally {
      setBusy(false);
    }
  }

  const sourceHref = (s: Source) => s.url ?? `/w/${workspaceId}${hitPath({ ...s, status: null, updated_at: null })}`;

  return (
    <div className="flex flex-col gap-6">
      {turns.length === 0 ? (
        <div className="panel-in flex flex-col items-center gap-4 py-8 text-center">
          <span className="bg-primary/10 text-primary flex size-12 items-center justify-center rounded-2xl">
            <Sparkles aria-hidden className="size-6" />
          </span>
          <p className="text-muted-foreground max-w-md text-sm">
            Relay searches responsibilities, knowledge, cases, people, risks and synced GitHub and
            Linear work, then answers with citations you can open.
          </p>
          <div className="flex flex-wrap justify-center gap-2">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => ask(s)}
                className="bg-card hover:border-primary/40 rounded-full border px-3 py-1.5 text-sm transition-colors"
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      {turns.map((t, i) => {
        const cited = new Set(t.final?.cited ?? []);
        const text = t.final ? t.final.answer : t.draft;
        return (
          <article key={i} className="panel-in flex flex-col gap-3">
            <p className="bg-muted ml-auto max-w-[85%] rounded-2xl rounded-br-sm px-4 py-2 text-sm">
              {t.question}
            </p>
            <div className="bg-card rounded-xl border p-4 text-sm">
              {t.final && t.final.mode !== "ai" ? (
                <Badge tone={t.final.mode === "search" ? "warning" : "muted"} className="mb-2">
                  {t.final.mode === "search"
                    ? "Matching records, not an AI answer"
                    : "Not in the records"}
                </Badge>
              ) : null}
              {text ? (
                <p className="leading-relaxed whitespace-pre-wrap">
                  {text}
                  {!t.final && !t.error ? <span className="copilot-caret" aria-hidden /> : null}
                </p>
              ) : !t.error ? (
                <p className="text-muted-foreground flex items-center gap-2">
                  <span className="copilot-pulse" aria-hidden />
                  {t.sources.length
                    ? `Reading ${t.sources.length} records…`
                    : "Searching the workspace…"}
                </p>
              ) : null}
              {t.final?.note ? (
                <p className="text-muted-foreground mt-2 text-xs">{t.final.note}</p>
              ) : null}
              {t.error ? (
                <p role="alert" className="mt-2 text-amber-700 dark:text-amber-300">
                  {t.error}
                </p>
              ) : null}
              {t.sources.length ? (
                <ul className="mt-3 flex flex-wrap gap-1.5 border-t pt-3" aria-label="Sources">
                  {t.sources
                    .filter((s) => !t.final || cited.has(s.ref) || t.final.mode === "not_found")
                    .slice(0, t.final?.mode === "not_found" ? 4 : 12)
                    .map((s) => (
                      <li key={s.ref}>
                        <Link
                          href={sourceHref(s)}
                          title={s.detail ?? s.title}
                          className={cn(
                            "inline-flex max-w-72 items-center gap-1.5 rounded-md border px-2 py-1 text-xs transition-colors",
                            cited.has(s.ref)
                              ? "border-primary/40 bg-primary/5 hover:bg-primary/10"
                              : "text-muted-foreground hover:text-foreground",
                          )}
                        >
                          <span className="text-primary font-mono">{s.ref}</span>
                          <span className="truncate">{s.title}</span>
                          <span className="text-muted-foreground shrink-0">
                            {KIND_LABEL[s.kind]}
                          </span>
                          <ArrowUpRight aria-hidden className="size-3 shrink-0" />
                        </Link>
                      </li>
                    ))}
                </ul>
              ) : null}
            </div>
          </article>
        );
      })}

      <form
        onSubmit={(e) => ask(question, e)}
        className="bg-background/90 sticky bottom-4 flex gap-2 rounded-xl border p-2 shadow-sm backdrop-blur"
      >
        <label htmlFor="ask" className="sr-only">
          Your question
        </label>
        <input
          id="ask"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          maxLength={500}
          placeholder="Ask about owners, decisions, risks, how things work…"
          className={cn(inputClass, "flex-1 border-0 shadow-none focus-visible:ring-0")}
        />
        {busy ? (
          <Button type="button" variant="outline" onClick={() => abort.current?.abort()}>
            <Square aria-hidden className="size-3.5" /> Stop
          </Button>
        ) : (
          <Button type="submit" disabled={question.trim().length < 3}>
            <SendHorizontal aria-hidden className="size-4" /> Ask
          </Button>
        )}
      </form>
    </div>
  );
}
