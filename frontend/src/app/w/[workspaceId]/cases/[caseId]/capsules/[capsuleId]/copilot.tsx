"use client";

import { MessageSquareText, SendHorizontal, Square } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";

import { inputClass } from "@/components/action-form";
import { EvidenceList } from "@/components/ai";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { AnswerView } from "@/lib/types";
import { cn } from "@/lib/utils";

const MODE = {
  ai: { label: "Answer from the evidence", tone: "neutral" },
  search: { label: "Search results, not an answer", tone: "warning" },
  not_found: { label: "Not in the evidence", tone: "muted" },
} as const;

const SUGGESTIONS = [
  "What should I do in my first week?",
  "Which decisions were already made, and why?",
  "Who do I escalate to if something breaks?",
  "What information is missing from this handover?",
];

const time = new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short" });

type Source = {
  ref: string;
  title: string;
  source_system: string;
  source_type: string;
  url: string | null;
};

type Live = { question: string; sources: Source[] | null; text: string };

/** Parses a server-sent event stream into (event, data) pairs as the bytes arrive. */
async function* events(body: ReadableStream<Uint8Array>) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) return;
    buffer += decoder.decode(value, { stream: true });
    let end;
    while ((end = buffer.indexOf("\n\n")) >= 0) {
      const block = buffer.slice(0, end);
      buffer = buffer.slice(end + 2);
      const event = /^event: (.*)$/m.exec(block)?.[1];
      const data = /^data: (.*)$/m.exec(block)?.[1];
      if (event && data) yield { event, data: JSON.parse(data) as unknown };
    }
  }
}

/** The draft as the model writes it: format markers hidden, refs shown as source chips. */
function Draft({ text, sources }: { text: string; sources: Source[] }) {
  const clean = text
    .replaceAll("**", "")
    .replace(/^\s*NOT_FOUND\s*:?\s*/i, "")
    .replace(/\n?\s*confidence:\s*\w*\W*$/i, "");
  const byRef = new Map(sources.map((s) => [s.ref.toUpperCase(), s]));
  const parts: ReactNode[] = [];
  let last = 0;
  for (const m of clean.matchAll(/\s*\[\s*(E\d+(?:\s*,\s*E\d+)*)\s*\]/gi)) {
    parts.push(clean.slice(last, m.index));
    for (const ref of m[1].split(",").map((r) => r.trim().toUpperCase())) {
      const source = byRef.get(ref);
      parts.push(
        <sup
          key={`${m.index}-${ref}`}
          title={source ? source.title : "Not one of the sources: this won't be kept"}
          className={cn(
            "mx-0.5 rounded px-1 text-[10px] font-medium",
            source ? "bg-accent text-accent-foreground" : "bg-destructive/10 text-destructive",
          )}
        >
          {ref}
        </sup>,
      );
    }
    last = (m.index ?? 0) + m[0].length;
  }
  parts.push(clean.slice(last));
  return (
    <p className="whitespace-pre-line">
      {parts}
      <span aria-hidden className="copilot-caret" />
    </p>
  );
}

/** Ask the handover: answers come only from the evidence the brief was built from. */
export function Copilot({
  workspaceId,
  capsuleId,
  caseId,
  initial,
}: {
  workspaceId: string;
  capsuleId: string;
  caseId: string;
  initial: AnswerView[];
}) {
  const [draft, setDraft] = useState("");
  const [thread, setThread] = useState(initial);
  const [live, setLive] = useState<Live | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abort = useRef<AbortController | null>(null);
  const log = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);

  // Follow the answer as it is written, and the newest answer once it lands.
  useEffect(() => {
    log.current?.scrollTo({ top: log.current.scrollHeight, behavior: "smooth" });
  }, [thread.length, live?.sources, live?.text]);

  useEffect(() => () => abort.current?.abort(), []);

  async function ask(question: string) {
    const controller = new AbortController();
    abort.current = controller;
    setError(null);
    setLive({ question, sources: null, text: "" });
    try {
      const response = await fetch(`/w/${workspaceId}/cases/${caseId}/capsules/${capsuleId}/ask`, {
        method: "POST",
        body: JSON.stringify({ question }),
        headers: { "Content-Type": "application/json" },
        signal: controller.signal,
      });
      if (!response.ok || !response.body) {
        const problem = (await response.json().catch(() => ({}))) as { detail?: string };
        throw new Error(problem.detail ?? "The question could not be sent. Try again.");
      }
      for await (const { event, data } of events(response.body)) {
        if (event === "evidence") {
          const { sources } = data as { sources: Source[] };
          setLive((l) => l && { ...l, sources });
        } else if (event === "delta") {
          const { text } = data as { text: string };
          setLive((l) => l && { ...l, text: l.text + text });
        } else if (event === "final") {
          setThread((t) => [...t, data as AnswerView]);
          setDraft("");
        } else if (event === "error") {
          throw new Error((data as { message: string }).message);
        }
      }
    } catch (e) {
      if (controller.signal.aborted) {
        setError("Stopped. Nothing from that answer was kept.");
        setDraft(question);
      } else {
        setError(e instanceof Error ? e.message : "Something went wrong. Try again.");
        setDraft(question);
      }
    } finally {
      setLive(null);
      abort.current = null;
      input.current?.focus();
    }
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    const question = draft.trim();
    if (question.length >= 3 && !live) void ask(question);
  }

  return (
    <section
      aria-labelledby="copilot-heading"
      className="bg-card flex flex-col rounded-lg border shadow-xs"
    >
      <div className="flex items-start gap-3 border-b p-4">
        <span className="bg-accent text-accent-foreground flex size-8 shrink-0 items-center justify-center rounded-md">
          <MessageSquareText aria-hidden className="size-4" />
        </span>
        <div>
          <h2 id="copilot-heading" className="text-sm font-semibold">
            Ask about this handover
          </h2>
          <p className="text-muted-foreground text-xs">
            Answers use only the sources behind this brief that you can see, and cite them. If the
            sources don&apos;t say, it tells you so instead of guessing.
          </p>
        </div>
      </div>

      <div
        ref={log}
        aria-live="polite"
        aria-busy={live !== null}
        className="flex max-h-[32rem] flex-col gap-4 overflow-y-auto p-4"
      >
        {thread.length === 0 && !live ? (
          <div className="flex flex-col gap-2">
            <p className="text-muted-foreground text-xs">Try one of these:</p>
            <div className="flex flex-wrap gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => {
                    setDraft(s);
                    input.current?.focus();
                  }}
                  className="hover:bg-muted rounded-full border px-3 py-1 text-xs transition-colors duration-150 active:scale-[0.98]"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : null}
        {thread.map((q) => (
          <article key={q.id} className="copilot-turn flex flex-col gap-2">
            <Question text={q.question} />
            <div
              className={cn(
                "flex max-w-[95%] flex-col gap-1.5 rounded-lg rounded-bl-sm border px-3 py-2.5 text-sm",
                q.mode === "ai" ? "bg-background" : "bg-muted/40",
              )}
            >
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={MODE[q.mode].tone}>{MODE[q.mode].label}</Badge>
                {q.confidence ? (
                  <span className="text-muted-foreground text-xs">{q.confidence} confidence</span>
                ) : null}
              </div>
              <p className="whitespace-pre-line">{q.answer}</p>
              {q.note ? <p className="text-muted-foreground text-xs">{q.note}</p> : null}
              {q.evidence.length > 0 ? (
                <div>
                  {q.mode !== "ai" ? (
                    <p className="text-muted-foreground mb-1 text-xs">
                      {q.mode === "not_found"
                        ? "Closest sources to check:"
                        : "Sources that mention it:"}
                    </p>
                  ) : null}
                  <EvidenceList evidence={q.evidence} />
                </div>
              ) : null}
              {q.withdrawn_sources > 0 ? (
                <p className="text-muted-foreground text-xs">
                  {q.withdrawn_sources} cited source
                  {q.withdrawn_sources === 1 ? " is" : "s are"} no longer available.
                </p>
              ) : null}
              <p className="text-muted-foreground text-[11px]">
                {q.asked_by} · {time.format(new Date(q.asked_at))} · brief v{q.capsule_version}
              </p>
            </div>
          </article>
        ))}
        {live ? (
          <article className="copilot-turn flex flex-col gap-2">
            <Question text={live.question} />
            <div className="bg-background flex max-w-[95%] flex-col gap-2 rounded-lg rounded-bl-sm border px-3 py-2.5 text-sm">
              {live.sources === null ? (
                <p role="status" className="text-muted-foreground flex items-center gap-2 text-xs">
                  <span aria-hidden className="copilot-pulse" />
                  Gathering the sources you can see…
                </p>
              ) : (
                <div role="status" className="flex flex-col gap-1.5">
                  <p className="text-muted-foreground flex items-center gap-2 text-xs">
                    {live.text ? null : <span aria-hidden className="copilot-pulse" />}
                    Reading {live.sources.length} source
                    {live.sources.length === 1 ? "" : "s"}
                    {live.text ? "" : "…"}
                  </p>
                  <ul className="flex flex-wrap gap-1">
                    {live.sources.slice(0, 8).map((s, i) => (
                      <li
                        key={s.ref}
                        style={{ animationDelay: `${i * 40}ms` }}
                        className="copilot-source bg-muted text-muted-foreground max-w-48 truncate rounded px-1.5 py-0.5 text-[11px]"
                        title={`${s.source_system} · ${s.title}`}
                      >
                        <span className="text-foreground font-medium">{s.ref}</span> {s.title}
                      </li>
                    ))}
                    {live.sources.length > 8 ? (
                      <li className="text-muted-foreground px-1 text-[11px]">
                        +{live.sources.length - 8} more
                      </li>
                    ) : null}
                  </ul>
                </div>
              )}
              {live.text ? <Draft text={live.text} sources={live.sources ?? []} /> : null}
              {live.text ? (
                <p className="text-muted-foreground text-[11px]">
                  Draft. Citations are checked before the answer is kept.
                </p>
              ) : null}
            </div>
          </article>
        ) : null}
      </div>

      <form onSubmit={submit} className="flex flex-col gap-2 border-t p-3">
        <div className="flex gap-2">
          <label htmlFor="copilot-question" className="sr-only">
            Your question
          </label>
          <input
            ref={input}
            id="copilot-question"
            name="question"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            maxLength={500}
            required
            autoComplete="off"
            placeholder="e.g. How do I roll back a bad deploy?"
            className={inputClass}
          />
          {live ? (
            <Button type="button" variant="outline" onClick={() => abort.current?.abort()}>
              <Square aria-hidden className="fill-current" />
              Stop
            </Button>
          ) : (
            <Button type="submit" disabled={draft.trim().length < 3}>
              <SendHorizontal aria-hidden />
              Ask
            </Button>
          )}
        </div>
        {error ? (
          <p role="alert" className="text-muted-foreground text-sm">
            {error}
          </p>
        ) : null}
        <p className="text-muted-foreground text-[11px]">
          Questions and answers are kept with this handover and visible to its editors.
        </p>
      </form>
    </section>
  );
}

function Question({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <p className="bg-secondary max-w-[85%] rounded-lg rounded-br-sm px-3 py-2 text-sm">{text}</p>
    </div>
  );
}
