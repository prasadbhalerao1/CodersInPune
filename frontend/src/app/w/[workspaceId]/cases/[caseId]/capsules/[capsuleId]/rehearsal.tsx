"use client";

import { Check, Dumbbell, RotateCcw, X } from "lucide-react";
import { useState, useTransition } from "react";

import { inputClass } from "@/components/action-form";
import { Explain } from "@/components/explain";
import { Button } from "@/components/ui/button";
import type { RehearsalDrill, RehearsalGrade } from "@/lib/types";
import { cn } from "@/lib/utils";

import { gradeRehearsalAction } from "./rehearsal-actions";

const VERDICT = {
  ready: { label: "Ready", tone: "text-emerald-700 dark:text-emerald-300" },
  partly: { label: "Partly there", tone: "text-amber-700 dark:text-amber-300" },
  not_yet: { label: "Not yet", tone: "text-red-700 dark:text-red-300" },
} as const;

/**
 * Practise the handover before you need it: answer drills built from the brief's evidence;
 * each answer is checked against the source and shows what you missed and where to read.
 */
export function Rehearsal({
  workspaceId,
  capsuleId,
  drills,
}: {
  workspaceId: string;
  capsuleId: string;
  drills: RehearsalDrill[];
}) {
  const [at, setAt] = useState(0);
  const [answer, setAnswer] = useState("");
  const [grades, setGrades] = useState<Record<string, RehearsalGrade>>({});
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  if (!drills.length) return null;
  const drill = drills[at];
  const grade = grades[drill.id];
  const done = Object.values(grades);
  const average = done.length
    ? Math.round(done.reduce((sum, g) => sum + g.score, 0) / done.length)
    : null;

  function submit() {
    setError(null);
    start(async () => {
      const result = await gradeRehearsalAction(workspaceId, capsuleId, drill.id, answer);
      if (result.grade) setGrades((g) => ({ ...g, [drill.id]: result.grade! }));
      else setError(result.error ?? "The answer could not be checked.");
    });
  }

  function go(next: number) {
    setAt(next);
    setAnswer("");
    setError(null);
  }

  return (
    <section aria-labelledby="rehearsal" className="bg-card rounded-xl border p-4 text-sm">
      <div className="flex items-center gap-2">
        <Dumbbell aria-hidden className="text-primary size-4" />
        <h2 id="rehearsal" className="font-semibold">
          Rehearse this handover
        </h2>
        <Explain what="rehearsal" align="end" />
        <span className="text-muted-foreground ml-auto text-xs tabular-nums">
          {at + 1} / {drills.length}
          {average !== null ? ` · average ${average}` : ""}
        </span>
      </div>
      <p className="mt-3 font-medium">{drill.prompt}</p>
      {grade ? (
        <div className="panel-in mt-3 flex flex-col gap-2">
          <p className={cn("font-semibold", VERDICT[grade.verdict].tone)}>
            {VERDICT[grade.verdict].label} · {grade.score}/100
          </p>
          <div className="flex flex-wrap gap-1">
            {grade.covered.map((t) => (
              <span
                key={t}
                className="inline-flex items-center gap-1 rounded bg-emerald-50 px-1.5 py-0.5 text-xs text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-200"
              >
                <Check aria-hidden className="size-3" /> {t}
              </span>
            ))}
            {grade.missed.map((t) => (
              <span
                key={t}
                className="inline-flex items-center gap-1 rounded bg-red-50 px-1.5 py-0.5 text-xs text-red-800 dark:bg-red-950/40 dark:text-red-200"
              >
                <X aria-hidden className="size-3" /> {t}
              </span>
            ))}
          </div>
          <blockquote className="text-muted-foreground border-l-2 pl-3 text-xs whitespace-pre-line">
            <span className="text-foreground font-medium">From “{grade.source_title}”: </span>
            {grade.source_excerpt}
          </blockquote>
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={() =>
                setGrades((g) =>
                  Object.fromEntries(Object.entries(g).filter(([k]) => k !== drill.id)),
                )
              }
            >
              <RotateCcw aria-hidden className="size-3.5" /> Try again
            </Button>
            {at + 1 < drills.length ? (
              <Button size="sm" onClick={() => go(at + 1)}>
                Next drill
              </Button>
            ) : (
              <Button size="sm" variant="ghost" onClick={() => go(0)}>
                Start over
              </Button>
            )}
          </div>
        </div>
      ) : (
        <div className="mt-3 flex flex-col gap-2">
          <textarea
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            rows={3}
            maxLength={4000}
            aria-label="Your answer"
            placeholder="Answer from memory, as you would on the day."
            className={cn(inputClass, "h-auto py-2")}
          />
          {error ? (
            <p role="alert" className="text-xs text-amber-700 dark:text-amber-300">
              {error}
            </p>
          ) : null}
          <div className="flex gap-2">
            <Button size="sm" onClick={submit} disabled={pending || !answer.trim()}>
              {pending ? "Checking…" : "Check my answer"}
            </Button>
            {at + 1 < drills.length ? (
              <Button size="sm" variant="ghost" onClick={() => go(at + 1)}>
                Skip
              </Button>
            ) : null}
          </div>
        </div>
      )}
    </section>
  );
}
