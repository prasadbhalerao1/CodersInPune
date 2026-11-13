"use client";

import { useEffect } from "react";

// Wheel and trackpad gestures advance exactly one stop, however hard they are thrown.
// Stops are the top of every snap section plus one screen at a time through sections that are
// taller than the viewport, so nothing is ever skipped and the step size is always the same.
// Touch devices keep native scrolling (with CSS mandatory snapping); reduced motion keeps
// plain scrolling; scrollbar drags and in-page links are untouched.

const MIN_TWEEN = 550;
const MAX_TWEEN = 900;
const QUIET_MS = 140; // wheel events keep coming during trackpad inertia; wait for them to stop
const FAILSAFE_MS = 2600;

function collectStops(): number[] {
  const vh = window.innerHeight;
  const max = Math.max(0, document.documentElement.scrollHeight - vh);
  const stops = new Set<number>([0, Math.round(max)]);
  document.querySelectorAll<HTMLElement>("[class*='snap-start']").forEach((el) => {
    const cs = getComputedStyle(el);
    if (cs.scrollSnapAlign === "none" || cs.display === "none") return;
    const rect = el.getBoundingClientRect();
    const top = Math.round(rect.top + window.scrollY - (parseFloat(cs.scrollMarginTop) || 0));
    if (top > max) return;
    stops.add(Math.max(0, top));
    if (rect.height > vh * 1.25) {
      const step = vh * 0.85;
      for (let y = top + step; y < top + rect.height - vh * 0.2; y += step) {
        stops.add(Math.round(Math.min(y, max)));
      }
    }
  });
  return [...stops].sort((a, b) => a - b);
}

const ease = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);

export function ScrollPaging() {
  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const coarse = window.matchMedia("(pointer: coarse)").matches;
    if (reduced || coarse) return;

    let locked = false;
    let lastWheel = 0;
    let raf = 0;
    let failsafe = 0;
    let poll = 0;

    const unlock = () => {
      locked = false;
      clearTimeout(failsafe);
      clearTimeout(poll);
    };

    const settle = () => {
      // Stay locked until the gesture (including inertia) has really stopped.
      if (performance.now() - lastWheel > QUIET_MS) unlock();
      else poll = window.setTimeout(settle, 50);
    };

    const go = (dir: 1 | -1) => {
      const y = window.scrollY;
      const stops = collectStops();
      const target =
        dir > 0 ? stops.find((s) => s > y + 6) : [...stops].reverse().find((s) => s < y - 6);
      if (target === undefined) return;
      locked = true;
      failsafe = window.setTimeout(unlock, FAILSAFE_MS);
      const dist = target - y;
      const dur = Math.min(MAX_TWEEN, Math.max(MIN_TWEEN, Math.abs(dist) * 0.6));
      const t0 = performance.now();
      const step = (now: number) => {
        const t = Math.min(1, (now - t0) / dur);
        window.scrollTo({ top: y + dist * ease(t), behavior: "instant" });
        if (t < 1) raf = requestAnimationFrame(step);
        else settle();
      };
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(step);
    };

    const onWheel = (e: WheelEvent) => {
      if (e.ctrlKey || e.defaultPrevented) return; // pinch-zoom and handled events
      if (Math.abs(e.deltaX) > Math.abs(e.deltaY)) return; // horizontal gestures untouched
      if ((e.target as HTMLElement | null)?.closest?.("[data-no-paging]")) return;
      e.preventDefault();
      lastWheel = performance.now();
      if (locked || Math.abs(e.deltaY) < 4) return;
      go(e.deltaY > 0 ? 1 : -1);
    };

    const onKey = (e: KeyboardEvent) => {
      if (e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey) return;
      const t = e.target as HTMLElement | null;
      if (t && t !== document.body && t.tagName !== "HTML") return; // leave form fields and buttons alone
      const down = e.key === "PageDown" || (e.key === " " && !e.shiftKey);
      const up = e.key === "PageUp" || (e.key === " " && e.shiftKey);
      if (!down && !up) return;
      e.preventDefault();
      lastWheel = performance.now();
      if (!locked) go(down ? 1 : -1);
    };

    window.addEventListener("wheel", onWheel, { passive: false });
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("wheel", onWheel);
      window.removeEventListener("keydown", onKey);
      cancelAnimationFrame(raf);
      clearTimeout(failsafe);
      clearTimeout(poll);
    };
  }, []);

  return null;
}
