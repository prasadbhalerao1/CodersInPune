"use client";

import { useEffect, useRef, useSyncExternalStore } from "react";

import { readInk, type Ink } from "./canvas";
import { finished, register } from "./director";
import { stageCanvas } from "./filmkit";
import { FIGURES_ON } from "./stage";

export type Running = {
  /** Advance; return true when the film is over. */
  step: (dt: number) => boolean;
  draw: (ctx: CanvasRenderingContext2D, ink: Ink) => void;
  /** Put the page back exactly as it was. Called on finish and on abort. */
  cleanup: () => void;
};

export type Script = {
  name: string;
  idleAfter: number;
  priority?: number;
  /** Draw in viewport space above the fixed header, instead of in document space. */
  fixed?: boolean;
  ready: () => boolean;
  start: () => Running;
};

/** Hosts one film: a canvas, registration with the director, a frame loop only while playing. */
export function FilmLayer({ script }: { script: Script }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const cv = canvas.current;
    if (!cv) return;
    const stage = stageCanvas(cv);
    let run: Running | null = null;
    let raf = 0;
    let last = 0;
    const stop = () => {
      cancelAnimationFrame(raf);
      raf = 0;
      run?.cleanup();
      run = null;
      stage.clear();
      finished(script.name);
    };
    const frame = (now: number) => {
      if (!run) return;
      const dt = last ? Math.min(0.033, (now - last) / 1000) : 0;
      last = now;
      raf = requestAnimationFrame(frame);
      if (dt === 0) return;
      const done = run.step(dt);
      stage.begin(!!script.fixed);
      run.draw(stage.ctx, readInk());
      if (done) stop();
    };
    const onResize = () => stage.fit();
    window.addEventListener("resize", onResize);
    const unregister = register({
      name: script.name,
      idleAfter: script.idleAfter,
      priority: script.priority,
      ready: script.ready,
      start: () => {
        run = script.start();
        last = 0;
        raf = requestAnimationFrame(frame);
      },
      abort: () => {
        if (run) stop();
      },
    });
    return () => {
      window.removeEventListener("resize", onResize);
      if (run) stop();
      unregister();
    };
  }, [script]);
  return (
    <canvas
      ref={canvas}
      aria-hidden
      data-film={script.name}
      className={`pointer-events-none fixed inset-0 ${script.fixed ? "z-[60]" : "z-40"}`}
      style={{ width: "100vw", height: "100vh" }}
    />
  );
}

export function useMotionAllowed() {
  return useSyncExternalStore(
    (cb) => {
      const m = window.matchMedia("(prefers-reduced-motion: reduce)");
      m.addEventListener("change", cb);
      return () => m.removeEventListener("change", cb);
    },
    () => !window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    () => false,
  );
}

export const filmsOn = FIGURES_ON;
