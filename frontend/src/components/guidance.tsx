"use client";

import { Check, Circle, Lightbulb, Play, RotateCcw, X } from "lucide-react";
import Link from "next/link";
import { useOptimistic, useTransition } from "react";

import { updateGuidanceAction } from "@/app/w/[workspaceId]/guidance-actions";
import { Button } from "@/components/ui/button";
import { TOURS } from "@/lib/tours";
import type { ChecklistItem, GuidanceUpdate, GuidanceView, TourView } from "@/lib/types";
import { cn } from "@/lib/utils";

const INTEGRATION_LABEL = {
  not_connected: "Not connected",
  sync_pending: "First sync pending",
  syncing: "Syncing",
  retrying: "Retrying a failed sync",
  attention: "Needs attention",
  ready: "Ready",
} as const;

function useGuidance(workspaceId: string) {
  const [pending, start] = useTransition();
  const send = (body: GuidanceUpdate) => start(() => void updateGuidanceAction(workspaceId, body));
  return { pending, send };
}

export function tourHref(t: TourView) {
  if (!t.path) return null;
  const step = !t.completed && t.resume_step ? `&step=${t.resume_step}` : "";
  return `${t.path}${t.path.includes("?") ? "&" : "?"}tour=${t.id}${step}`;
}

/** The per-member switch for automatic guidance. Tutorials stay available either way. */
export function GuidanceSwitch({
  workspaceId,
  enabled,
}: {
  workspaceId: string;
  enabled: boolean;
}) {
  const [on, setOn] = useOptimistic(enabled);
  const [pending, start] = useTransition();
  return (
    <label className="flex items-start gap-3 rounded-lg border p-4">
      <button
        type="button"
        role="switch"
        aria-checked={on}
        aria-label="Product guidance"
        disabled={pending}
        onClick={() =>
          start(async () => {
            setOn(!on);
            await updateGuidanceAction(workspaceId, { enabled: !on });
          })
        }
        className={cn(
          "relative mt-0.5 inline-flex h-5 w-9 shrink-0 rounded-full transition-colors",
          on ? "bg-primary" : "bg-muted-foreground/30",
        )}
      >
        <span
          className={cn(
            "bg-background absolute top-0.5 size-4 rounded-full shadow transition-transform",
            on ? "translate-x-4.5" : "translate-x-0.5",
          )}
        />
      </button>
      <span className="flex flex-col gap-0.5 text-sm">
        <span className="font-medium">Product guidance: {on ? "On" : "Off"}</span>
        <span className="text-muted-foreground">
          {on
            ? "Relay suggests a short tour when a feature becomes useful for your workspace, and shows the setup checklist on the Overview."
            : "No automatic tips or checklist. Every tutorial below still works whenever you start it."}
        </span>
      </span>
    </label>
  );
}

export function TourList({ workspaceId, tours }: { workspaceId: string; tours: TourView[] }) {
  const { pending, send } = useGuidance(workspaceId);
  return (
    <div className="flex flex-col gap-3">
      <ul className="bg-card divide-y rounded-lg border text-sm">
        {tours.map((t) => {
          const tour = TOURS[t.id];
          const href = tourHref(t);
          return (
            <li key={t.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
              {t.completed ? (
                <Check aria-label="Completed" className="text-primary size-4 shrink-0" />
              ) : (
                <Circle aria-hidden className="text-muted-foreground/50 size-4 shrink-0" />
              )}
              <span className="min-w-0 flex-1">
                <span className="font-medium">{tour.title}</span>{" "}
                <span className="text-muted-foreground text-xs">· {tour.minutes} min</span>
                <span className="text-muted-foreground block">{tour.summary}</span>
                {!t.eligible && t.reason ? (
                  <span className="text-muted-foreground block text-xs italic">{t.reason}</span>
                ) : null}
              </span>
              {href ? (
                <Link
                  href={href}
                  className="text-primary inline-flex items-center gap-1 text-xs font-medium hover:underline"
                >
                  <Play aria-hidden className="size-3" />
                  {t.completed ? "Replay" : t.resume_step ? "Resume" : "Start"}
                </Link>
              ) : (
                <span className="text-muted-foreground text-xs">Not available yet</span>
              )}
            </li>
          );
        })}
      </ul>
      <div>
        <Button
          size="sm"
          variant="ghost"
          disabled={pending}
          onClick={() => send({ reset: true })}
          className="gap-1.5"
        >
          <RotateCcw aria-hidden className="size-3.5" />
          Restart tutorial progress
        </Button>
        <span className="text-muted-foreground text-xs">
          Clears finished and paused tours only; your workspace data is untouched.
        </span>
      </div>
    </div>
  );
}

export function Checklist({ items }: { items: ChecklistItem[] }) {
  const groups: [string, ChecklistItem[]][] = [
    ["Essentials", items.filter((i) => i.essential)],
    ["Optional: connect your tools", items.filter((i) => !i.essential)],
  ];
  return (
    <div className="grid gap-4 md:grid-cols-2">
      {groups.map(([label, list]) => (
        <div key={label} className="flex flex-col gap-1.5">
          <h3 className="text-muted-foreground text-xs font-medium">
            {label} · {list.filter((i) => i.done).length} of {list.length}
          </h3>
          <ul className="flex flex-col gap-0.5 text-sm">
            {list.map((i) => (
              <li key={i.key}>
                <Link
                  href={i.path}
                  className="hover:bg-muted flex items-center gap-2 rounded-md px-2 py-1"
                >
                  {i.done ? (
                    <Check aria-label="Done" className="text-primary size-4 shrink-0" />
                  ) : (
                    <Circle
                      aria-label="To do"
                      className="text-muted-foreground/50 size-4 shrink-0"
                    />
                  )}
                  <span className={cn("flex-1", i.done && "text-muted-foreground")}>{i.label}</span>
                  {i.detail && !i.done ? (
                    <span className="text-muted-foreground truncate text-xs">{i.detail}</span>
                  ) : null}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

export function IntegrationStatus({ guidance }: { guidance: GuidanceView }) {
  return (
    <ul className="grid gap-2 sm:grid-cols-3">
      {guidance.integrations.map((i) => (
        <li key={i.provider} className="rounded-lg border p-3 text-sm">
          <span className="font-medium capitalize">{i.provider}</span>
          <span
            className={cn(
              "block text-xs font-medium",
              i.state === "ready" && "text-primary",
              i.state === "attention" && "text-red-700 dark:text-red-400",
              (i.state === "retrying" || i.state === "syncing") &&
                "text-amber-700 dark:text-amber-400",
            )}
          >
            {INTEGRATION_LABEL[i.state]}
          </span>
          <span className="text-muted-foreground block text-xs">{i.detail}</span>
        </li>
      ))}
    </ul>
  );
}

/** Overview panel shown only while guidance is on: the checklist and the next useful tour. */
export function GettingStarted({
  workspaceId,
  guidance,
}: {
  workspaceId: string;
  guidance: GuidanceView;
}) {
  const { pending, send } = useGuidance(workspaceId);
  if (!guidance.enabled) return null;
  const suggested = guidance.tours.find((t) => t.id === guidance.suggested);
  const href = suggested ? tourHref(suggested) : null;
  const showChecklist = !guidance.checklist_dismissed;
  if (!showChecklist && !href) return null;
  return (
    <section
      aria-label="Getting started"
      className="motion-page bg-card flex flex-col gap-4 rounded-lg border p-4 shadow-xs"
    >
      {suggested && href ? (
        <div className="flex flex-wrap items-center gap-3">
          <Lightbulb aria-hidden className="text-baton size-5 shrink-0" />
          <p className="min-w-0 flex-1 text-sm">
            <span className="font-medium">{TOURS[suggested.id].title}</span>{" "}
            <span className="text-muted-foreground">
              is ready for your workspace: a {TOURS[suggested.id].minutes}-minute tour.
            </span>
          </p>
          <Link
            href={href}
            className="bg-primary text-primary-foreground rounded-md px-3 py-1.5 text-xs font-medium"
          >
            {suggested.resume_step ? "Resume tour" : "Take the tour"}
          </Link>
          <Button
            size="sm"
            variant="ghost"
            disabled={pending}
            onClick={() => send({ dismiss: `tour:${suggested.id}` })}
          >
            Not now
          </Button>
        </div>
      ) : null}
      {showChecklist ? (
        <div className="flex flex-col gap-3">
          <div className="flex items-center gap-2">
            <h2 className="text-sm font-semibold">Set up continuity</h2>
            <Link
              href={`/w/${workspaceId}/help#learn`}
              className="text-primary text-xs font-medium hover:underline"
            >
              All tutorials and guidance settings
            </Link>
            <button
              type="button"
              disabled={pending}
              onClick={() => send({ dismiss: "checklist" })}
              aria-label="Hide the setup checklist"
              className="text-muted-foreground hover:text-foreground ml-auto rounded p-1"
            >
              <X className="size-4" />
            </button>
          </div>
          <Checklist items={guidance.checklist} />
        </div>
      ) : null}
    </section>
  );
}
