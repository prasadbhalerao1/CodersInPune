"use client";

import { MessageSquareText, SendHorizontal } from "lucide-react";
import { useActionState, useEffect, useRef, useState } from "react";

import { inputClass } from "@/components/action-form";
import { EvidenceList } from "@/components/ai";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { AnswerView } from "@/lib/types";
import { cn } from "@/lib/utils";

import { askCapsuleAction, type AskState } from "../../ai-actions";

const MODE = {
  ai: { label: "Answer from the evidence", tone: "neutral" },
  search: { label: "Search results, not an answer", tone: "warning" },
  not_found: { label: "Not in the evidence", tone: "muted" },
} as const;

const SUGGESTIONS = [
  "What should I do in my first week?",
  "Which decisions were already made, and why?",
  "Who do I escalate to if something breaks?",
];

const time = new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short" });

/** Ask the handover: answers come only from the evidence the brief was built from. */
export function Copilot({
  workspaceId,
  capsuleId,
  initial,
}: {
  workspaceId: string;
  capsuleId: string;
  initial: AnswerView[];
}) {
  const [draft, setDraft] = useState("");

  const [state, action, pending] = useActionState<AskState & { thread: AnswerView[] }, FormData>(
    async (previous, formData) => {
      const result = await askCapsuleAction(workspaceId, capsuleId, {}, formData);
      if (!result.answer) return { ...result, thread: previous.thread };
      setDraft("");
      return { thread: [...previous.thread, result.answer] };
    },
    { thread: initial },
  );
  const thread = state.thread;
  const log = useRef<HTMLDivElement>(null);
  // Keep the newest answer in view once it has rendered (and while one is pending).
  useEffect(() => {
    log.current?.scrollTo({ top: log.current.scrollHeight, behavior: "smooth" });
  }, [thread.length, pending]);

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

      <div ref={log} className="flex max-h-[32rem] flex-col gap-4 overflow-y-auto p-4">
        {thread.length === 0 ? (
          <div className="flex flex-col gap-2">
            <p className="text-muted-foreground text-xs">Try one of these:</p>
            <div className="flex flex-wrap gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => setDraft(s)}
                  className="hover:bg-muted rounded-full border px-3 py-1 text-xs"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          thread.map((q) => (
            <article key={q.id} className="flex flex-col gap-2">
              <div className="flex justify-end">
                <p className="bg-secondary max-w-[85%] rounded-lg rounded-br-sm px-3 py-2 text-sm">
                  {q.question}
                </p>
              </div>
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
                <p>{q.answer}</p>
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
          ))
        )}
        {pending ? (
          <p role="status" className="text-muted-foreground flex items-center gap-2 text-sm">
            <span
              aria-hidden
              className="border-muted-foreground/30 border-t-foreground inline-block size-3.5 animate-spin rounded-full border-2"
            />
            Checking the handover&apos;s sources…
          </p>
        ) : null}
      </div>

      <form action={action} className="flex flex-col gap-2 border-t p-3">
        <div className="flex gap-2">
          <label htmlFor="copilot-question" className="sr-only">
            Your question
          </label>
          <input
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
          <Button type="submit" disabled={pending || draft.trim().length < 3}>
            <SendHorizontal aria-hidden />
            Ask
          </Button>
        </div>
        {state.error ? (
          <p role="alert" className="text-destructive text-sm">
            {state.error}
          </p>
        ) : null}
        <p className="text-muted-foreground text-[11px]">
          Questions and answers are kept with this handover and visible to its editors.
        </p>
      </form>
    </section>
  );
}
