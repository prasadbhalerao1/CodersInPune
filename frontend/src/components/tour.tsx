"use client";

import { X } from "lucide-react";
import { useParams, usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { updateGuidanceAction } from "@/app/w/[workspaceId]/guidance-actions";
import { Button } from "@/components/ui/button";
import { TOURS } from "@/lib/tours";
import type { TourId } from "@/lib/types";

const CARD_WIDTH = 340;
const GAP = 12;

/** Runs the tour named by `?tour=` (resuming at `?step=`); mounted once per workspace. */
export function TourRunner() {
  const search = useSearchParams();
  const id = search.get("tour");
  if (!id || !(id in TOURS)) return null;
  const step = Number(search.get("step") ?? 0);
  return <TourCard key={id} id={id as TourId} start={Number.isInteger(step) ? step : 0} />;
}

function TourCard({ id, start }: { id: TourId; start: number }) {
  const tour = TOURS[id];
  const last = tour.steps.length - 1;
  const [index, setIndex] = useState(Math.min(Math.max(start, 0), last));
  const [rect, setRect] = useState<DOMRect | null>(null);
  const card = useRef<HTMLDivElement>(null);
  const router = useRouter();
  const pathname = usePathname();
  const { workspaceId } = useParams<{ workspaceId: string }>();
  const step = tour.steps[index];

  // Find the step's element (pages stream in, so look for a moment), bring it into view
  // and follow it while the page scrolls or resizes.
  useEffect(() => {
    let element: Element | null = null;
    let tries = 0;
    const measure = () => setRect(element ? element.getBoundingClientRect() : null);
    const find = window.setInterval(() => {
      element = step.target ? document.querySelector(step.target) : null;
      if (element || ++tries > 10) {
        window.clearInterval(find);
        const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        element?.scrollIntoView({ block: "center", behavior: reduce ? "auto" : "smooth" });
        measure();
      }
    }, 150);
    window.addEventListener("scroll", measure, true);
    window.addEventListener("resize", measure);
    return () => {
      window.clearInterval(find);
      window.removeEventListener("scroll", measure, true);
      window.removeEventListener("resize", measure);
    };
  }, [step.target]);

  useEffect(() => card.current?.focus(), [index]);

  const close = useCallback(
    (finished: boolean) => {
      void updateGuidanceAction(
        workspaceId,
        finished ? { complete: id } : { progress: [id, index] },
      );
      router.replace(pathname, { scroll: false });
    },
    [id, index, pathname, router, workspaceId],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") close(false);
      if (e.key === "ArrowRight" && index < last) setIndex(index + 1);
      if (e.key === "ArrowLeft" && index > 0) setIndex(index - 1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [close, index, last]);

  const position = place(rect);
  return (
    <>
      {rect ? (
        <div
          aria-hidden
          className="tour-spotlight pointer-events-none fixed z-40 rounded-lg"
          style={{
            top: rect.top - 6,
            left: rect.left - 6,
            width: rect.width + 12,
            height: rect.height + 12,
          }}
        />
      ) : (
        <div aria-hidden className="pointer-events-none fixed inset-0 z-40 bg-black/20" />
      )}
      <div
        ref={card}
        role="dialog"
        aria-labelledby="tour-title"
        aria-describedby="tour-body"
        tabIndex={-1}
        className="motion-page bg-card fixed z-50 flex flex-col gap-3 rounded-lg border p-4 shadow-lg outline-none"
        style={{ width: CARD_WIDTH, maxWidth: "calc(100vw - 32px)", ...position }}
      >
        <div className="flex items-start gap-2">
          <div className="min-w-0 flex-1">
            <p className="text-primary text-[11px] font-medium tracking-wide uppercase">
              {tour.title} · {index + 1} of {tour.steps.length}
            </p>
            <h2 id="tour-title" className="mt-0.5 font-semibold">
              {step.title}
            </h2>
          </div>
          <button
            type="button"
            onClick={() => close(false)}
            aria-label="Close tour (you can resume it from Learn Relay)"
            className="text-muted-foreground hover:text-foreground -m-1 rounded p-1"
          >
            <X className="size-4" />
          </button>
        </div>
        <p id="tour-body" className="text-muted-foreground text-sm">
          {step.body}
        </p>
        {step.target && !rect ? (
          <p className="text-muted-foreground text-xs italic">
            This part of the page isn&apos;t showing right now, so here is the gist.
          </p>
        ) : null}
        <div className="flex items-center gap-2">
          <div aria-hidden className="flex flex-1 gap-1">
            {tour.steps.map((s, i) => (
              <span
                key={s.title}
                className={i <= index ? "bg-primary h-1 w-4 rounded" : "bg-muted h-1 w-4 rounded"}
              />
            ))}
          </div>
          <Button size="sm" variant="ghost" onClick={() => close(false)}>
            Skip
          </Button>
          {index > 0 ? (
            <Button size="sm" variant="outline" onClick={() => setIndex(index - 1)}>
              Back
            </Button>
          ) : null}
          {index < last ? (
            <Button size="sm" onClick={() => setIndex(index + 1)}>
              Next
            </Button>
          ) : (
            <Button size="sm" onClick={() => close(true)}>
              Done
            </Button>
          )}
        </div>
      </div>
    </>
  );
}

// Below the element when there is room, otherwise above it; centred with no element.
function place(rect: DOMRect | null): React.CSSProperties {
  if (!rect || typeof window === "undefined") {
    return { left: "50%", top: "50%", transform: "translate(-50%, -50%)" };
  }
  const left = Math.min(Math.max(16, rect.left), window.innerWidth - CARD_WIDTH - 16);
  const below = rect.bottom + GAP;
  if (below + 220 < window.innerHeight) return { left, top: below };
  return { left, bottom: Math.max(16, window.innerHeight - rect.top + GAP) };
}
