"use client";

import { useEffect, useRef } from "react";

import { approach, dims, mix, sit, smooth, solve, wave, type Vec } from "./rig";
import { FigureGlyph, drawFigure, useStage, figure, FIGURES_ON } from "./stage";

type Ledge = { x: number; y: number; size: number };
type Sim = { t: number; arrive: number; waveW: number; near: boolean; visible: boolean };

/**
 * Someone sitting on the end of the E's top bar in the footer wordmark, legs over the edge,
 * hands planted behind them. They drop in once the wordmark has risen into view, and wave
 * when the pointer comes close. The ledge is measured from the font, so it follows the
 * wordmark at every size.
 */
function FooterSitterScene() {
  const svg = useRef<SVGSVGElement>(null);
  const ledge = useRef<Ledge | null>(null);
  const sim = useRef<Sim>({ t: 0, arrive: -1, waveW: 0, near: false, visible: false });

  const kick = useStage(svg, (dt, _w, _h, still) => {
    const l = ledge.current;
    if (!l) return;
    const s = sim.current;
    s.t += dt;
    if (s.arrive >= 0) s.arrive += dt;
    const shown = still ? 1 : s.arrive < 0 ? 0 : smooth(s.arrive / 0.5);
    s.waveW += ((s.near && !still ? 1 : 0) - s.waveW) * approach(dt, 6);

    const H = Math.min(70, Math.max(28, l.size * 0.17));
    const d = dims(H);
    const f = 1;
    let p = sit(still ? 0 : s.t);
    if (s.waveW > 0.01) {
      const wv = wave(s.t);
      p = mix(p, { ...p, shA: wv.shA, elA: wv.elA, head: -0.1 }, s.waveW);
    }
    // thighs along the bar, knees at its end, shins hanging over the gap after the E
    const drop = (1 - shown) * 0.6 * H;
    const pelvis: Vec = { x: l.x - d.thigh * 0.92, y: l.y - d.stroke * 0.6 - drop };
    const plant = (back: number) => ({ target: { x: pelvis.x - back * H, y: l.y - drop } });
    const j = solve(p, d, pelvis.x, l.y, f, {
      pelvisY: pelvis.y,
      reachA: s.waveW > 0.01 ? { ...plant(0.16), w: 1 - s.waveW } : plant(0.16),
      reachB: plant(0.24),
    });
    drawFigure(figure(svg.current, "f"), j, d, { opacity: shown });
  });

  useEffect(() => {
    const el = svg.current;
    const mark = el?.parentElement?.querySelector<HTMLElement>(".wordmark");
    const text = mark?.firstChild;
    if (!el || !mark || !text || text.nodeType !== Node.TEXT_NODE) return;

    // the top-right corner of the E's ink, from the font's own metrics
    const measure = () => {
      const cs = getComputedStyle(mark);
      const ctx = document.createElement("canvas").getContext("2d");
      if (!ctx) return;
      ctx.font = `${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
      const m = ctx.measureText("E");
      const range = document.createRange();
      range.setStart(text, 1);
      range.setEnd(text, 2);
      const r = range.getBoundingClientRect();
      const box = el.getBoundingClientRect();
      const baseline = r.top + m.fontBoundingBoxAscent;
      ledge.current = {
        x: r.left + m.actualBoundingBoxRight - box.left,
        y: baseline - m.actualBoundingBoxAscent - box.top,
        size: parseFloat(cs.fontSize),
      };
      kick();
    };
    let alive = true;
    void document.fonts.ready.then(() => alive && measure());
    const ro = new ResizeObserver(measure);
    ro.observe(mark);

    // arrive once the wordmark has risen into view (it reveals on scroll)
    const io = new IntersectionObserver(
      (entries) => {
        const e = entries[0];
        if (!e) return;
        sim.current.visible = e.isIntersecting;
        if (e.intersectionRatio >= 0.85 && sim.current.arrive < 0) sim.current.arrive = 0;
      },
      { threshold: [0, 0.85] },
    );
    io.observe(mark);

    const onMove = (e: PointerEvent) => {
      const l = ledge.current;
      if (!l || !sim.current.visible) return;
      const box = el.getBoundingClientRect();
      sim.current.near =
        Math.hypot(e.clientX - (box.left + l.x), e.clientY - (box.top + l.y)) < 220;
    };
    window.addEventListener("pointermove", onMove, { passive: true });
    return () => {
      alive = false;
      ro.disconnect();
      io.disconnect();
      window.removeEventListener("pointermove", onMove);
    };
  }, [kick]);

  return (
    <svg
      ref={svg}
      aria-hidden
      className="pointer-events-none absolute inset-0 z-10 h-full w-full overflow-visible"
    >
      <FigureGlyph name="f" />
    </svg>
  );
}

export function FooterSitter() {
  return FIGURES_ON ? <FooterSitterScene /> : null;
}
