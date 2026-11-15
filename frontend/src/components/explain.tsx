"use client";

import { Info } from "lucide-react";
import { useEffect, useId, useRef, useState, type CSSProperties, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { EXPLAIN, type ExplainKey } from "@/lib/explain";
import { cn } from "@/lib/utils";

const WIDTH = 360;
const GUTTER = 12;

/**
 * ⓘ next to a number: what it means and exactly how it is calculated, from the same registry
 * as the public guide. Opens on hover, focus or tap; Escape, scrolling or a click elsewhere
 * closes it. The panel is placed against the viewport, so a clipping parent (a truncated
 * heading, a scrolling card) can't hide it, and it never runs off-screen.
 */
export function Explain({
  what,
  align = "center",
  className,
  working,
}: {
  what: ExplainKey;
  /** This number's own working: the records and arithmetic behind the value on screen. */
  working?: ReactNode;
  align?: "start" | "center" | "end";
  className?: string;
}) {
  const entry = EXPLAIN[what];
  const [place, setPlace] = useState<CSSProperties | null>(null);
  const open = place !== null;
  const id = useId();
  const root = useRef<HTMLSpanElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLSpanElement>(null);
  const leave = useRef<number | undefined>(undefined);

  function show() {
    clearTimeout(leave.current);
    const r = button.current?.getBoundingClientRect();
    if (!r) return;
    const width = Math.min(WIDTH, window.innerWidth - 2 * GUTTER);
    const anchor =
      align === "start"
        ? r.left
        : align === "end"
          ? r.right - width
          : r.left + r.width / 2 - width / 2;
    const left = Math.max(GUTTER, Math.min(anchor, window.innerWidth - width - GUTTER));
    // Below the icon, unless that would run off the bottom and there is room above.
    const below = r.bottom + 6;
    const style: CSSProperties =
      below + 220 > window.innerHeight && r.top > 240
        ? { left, width, bottom: window.innerHeight - r.top + 6 }
        : { left, width, top: below };
    setPlace(style);
  }
  const hide = () => setPlace(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && hide();
    const onDown = (e: PointerEvent) => {
      const target = e.target as Node;
      if (!root.current?.contains(target) && !panel.current?.contains(target)) hide();
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onDown);
    window.addEventListener("scroll", hide, { capture: true, passive: true });
    window.addEventListener("resize", hide);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onDown);
      window.removeEventListener("scroll", hide, { capture: true });
      window.removeEventListener("resize", hide);
    };
  }, [open]);

  return (
    <span
      ref={root}
      className={cn("inline-flex align-middle", className)}
      onMouseEnter={show}
      onMouseLeave={() => {
        // A short grace period lets the pointer travel onto the panel.
        leave.current = window.setTimeout(hide, 120);
      }}
      onBlur={(e) => {
        const next = e.relatedTarget as Node | null;
        if (!root.current?.contains(next) && !panel.current?.contains(next)) hide();
      }}
    >
      <button
        ref={button}
        type="button"
        aria-label={`How ${entry.title.toLowerCase()} works`}
        aria-expanded={open}
        aria-describedby={open ? id : undefined}
        onClick={show}
        onFocus={show}
        className="explain-dot focus-visible:ring-ring/40 inline-flex size-5 items-center justify-center rounded-full outline-none focus-visible:ring-2"
      >
        <Info aria-hidden className="size-4" strokeWidth={2.25} />
      </button>
      {place
        ? createPortal(
            <span
              id={id}
              ref={panel}
              role="tooltip"
              onMouseEnter={() => clearTimeout(leave.current)}
              onMouseLeave={hide}
              style={place}
              className="explain-pop bg-popover text-popover-foreground fixed z-[60] flex flex-col gap-2 rounded-lg border p-3 text-left text-xs leading-relaxed font-normal tracking-normal whitespace-normal normal-case shadow-lg"
            >
              <span className="text-foreground text-[13px] font-semibold">{entry.title}</span>
              <span>{entry.summary}</span>
              {"formula" in entry && entry.formula ? (
                <span className="bg-muted/60 text-foreground rounded-md px-2 py-1.5">
                  {entry.formula}
                </span>
              ) : null}
              {working ? (
                <span className="flex flex-col gap-1 border-t pt-2">
                  <span className="text-foreground text-[11px] font-semibold">In this result</span>
                  {working}
                </span>
              ) : null}
              <a
                href={`/docs#${what}`}
                className="text-foreground font-medium underline underline-offset-2"
              >
                Inputs and how to read it →
              </a>
            </span>,
            document.body,
          )
        : null}
    </span>
  );
}
