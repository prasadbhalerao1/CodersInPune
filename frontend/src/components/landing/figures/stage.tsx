"use client";

import { useCallback, useEffect, useRef, type RefObject } from "react";

import { clamp01, type Dims, type Joints, type Vec } from "./rig";

/**
 * Rendering and timing for the figures. Each figure is a few SVG nodes updated in place every
 * frame (no React render per frame). The loop runs only while the stage is on screen, stops in
 * background tabs (requestAnimationFrame does), and never runs for reduced motion: those
 * visitors get a still that is redrawn when the scene's inputs change.
 */

/** Kill switch for the whole layer: NEXT_PUBLIC_RELAY_FIGURES=0 renders no figure anywhere. */
export const FIGURES_ON = process.env.NEXT_PUBLIC_RELAY_FIGURES !== "0";

/** dt in seconds; `still` asks the scene for a representative motionless frame. */
export type Frame = (dt: number, w: number, h: number, still: boolean) => void;

export function useStage(ref: RefObject<SVGSVGElement | null>, frame: Frame) {
  const frameRef = useRef(frame);
  useEffect(() => {
    frameRef.current = frame;
  });
  const kickRef = useRef<() => void>(() => {});

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let w = 0;
    let h = 0;
    let raf = 0;
    let last = 0;
    const measure = () => {
      const r = el.getBoundingClientRect();
      w = r.width;
      h = r.height;
    };
    const once = () => {
      if (w > 0) frameRef.current(0, w, h, reduce);
    };
    const loop = (now: number) => {
      // clamp so a stalled tab or a long task does not teleport anyone
      const dt = last ? Math.min(0.05, (now - last) / 1000) : 0;
      last = now;
      if (w > 0) frameRef.current(dt, w, h, false);
      raf = requestAnimationFrame(loop);
    };
    const start = () => {
      if (raf || reduce) return;
      last = 0;
      raf = requestAnimationFrame(loop);
    };
    const stop = () => {
      if (raf) cancelAnimationFrame(raf);
      raf = 0;
    };
    measure();
    const ro = new ResizeObserver(() => {
      measure();
      if (!raf) once();
    });
    const io = new IntersectionObserver(
      (entries) => (entries[0]?.isIntersecting ? start() : stop()),
      { rootMargin: "160px 0px" },
    );
    ro.observe(el);
    io.observe(el);
    kickRef.current = () => {
      if (!raf) once();
    };
    once();
    return () => {
      stop();
      ro.disconnect();
      io.disconnect();
      kickRef.current = () => {};
    };
  }, [ref]);

  /** Redraw now if the loop is not running (reduced motion, or off screen). */
  return useCallback(() => kickRef.current(), []);
}

const PARTS = [
  "farThigh",
  "farShin",
  "farUpper",
  "farFore",
  "torso",
  "nearThigh",
  "nearShin",
  "nearUpper",
  "nearFore",
  "head",
] as const;
type Part = (typeof PARTS)[number];

export type FigureEls = { g: SVGGElement; shadow: SVGEllipseElement } & Record<
  Part,
  SVGPathElement | SVGCircleElement
>;

const cache = new WeakMap<SVGSVGElement, Map<string, FigureEls>>();

/** The nodes of the figure named `name` inside `svg`, looked up once and cached. */
export function figure(svg: SVGSVGElement | null, name: string): FigureEls | null {
  if (!svg) return null;
  let byName = cache.get(svg);
  if (!byName) cache.set(svg, (byName = new Map()));
  const hit = byName.get(name);
  if (hit?.g.isConnected) return hit;
  const g = svg.querySelector<SVGGElement>(`g[data-fig="${name}"]`);
  const shadow = g?.querySelector<SVGEllipseElement>(".fig-shadow");
  if (!g || !shadow) return null;
  const els = { g, shadow } as FigureEls;
  for (const part of PARTS) {
    const el = g.querySelector<SVGPathElement | SVGCircleElement>(`[data-part="${part}"]`);
    if (!el) return null;
    els[part] = el;
  }
  byName.set(name, els);
  return els;
}

/**
 * One figure, drawn back to front like a cut-out: the ground shadow, the far leg and arm (dimmed,
 * for depth), the torso, the near leg and arm, the head as a ring. Every segment is its own
 * stroke with its own weight, heavier at the trunk and thighs and lighter at the forearms.
 */
export function FigureGlyph({ name }: { name: string }) {
  return (
    <g data-fig={name} className="fig-g">
      <ellipse className="fig-shadow" />
      <g className="fig-far">
        <path data-part="farThigh" className="fig" />
        <path data-part="farShin" className="fig" />
        <path data-part="farUpper" className="fig" />
        <path data-part="farFore" className="fig" />
      </g>
      <path data-part="torso" className="fig" />
      <path data-part="nearThigh" className="fig" />
      <path data-part="nearShin" className="fig" />
      <path data-part="nearUpper" className="fig" />
      <path data-part="nearFore" className="fig" />
      <circle data-part="head" className="fig-head" />
    </g>
  );
}

const n = (v: number) => Math.round(v * 10) / 10;
const pt = (p: Vec) => `${n(p.x)} ${n(p.y)}`;
const seg = (el: Element, a: Vec, b: Vec, w: number, tail = "") => {
  el.setAttribute("d", `M${pt(a)}L${pt(b)}${tail}`);
  el.setAttribute("stroke-width", String(n(w)));
};

export function drawFigure(
  f: FigureEls | null,
  j: Joints,
  d: Dims,
  o: { opacity?: number; groundY?: number } = {},
) {
  if (!f) return;
  seg(f.farThigh, j.pelvis, j.kneeB, d.wThigh);
  seg(f.farShin, j.kneeB, j.footB, d.wShin);
  seg(f.farUpper, j.shoulder, j.elbowB, d.wUpper);
  seg(f.farFore, j.elbowB, j.handB, d.wFore);
  seg(f.torso, j.pelvis, j.chest, d.wTorso);
  seg(f.nearThigh, j.pelvis, j.kneeA, d.wThigh);
  seg(f.nearShin, j.kneeA, j.footA, d.wShin);
  seg(f.nearUpper, j.shoulder, j.elbowA, d.wUpper);
  seg(f.nearFore, j.elbowA, j.handA, d.wFore);
  const head = f.head;
  head.setAttribute("cx", String(n(j.head.x)));
  head.setAttribute("cy", String(n(j.head.y)));
  head.setAttribute("r", String(n(d.head)));
  f.g.style.opacity = String(clamp01(o.opacity ?? 1));
  const shadow = f.shadow;
  if (o.groundY === undefined) {
    shadow.setAttribute("rx", "0");
    return;
  }
  // the shadow sits under the feet and tightens as the figure leaves the ground
  const air = clamp01((o.groundY - Math.max(j.footA.y, j.footB.y)) / (0.5 * d.H));
  shadow.setAttribute("cx", String(n((j.footA.x + j.footB.x) / 2)));
  shadow.setAttribute("cy", String(n(o.groundY)));
  shadow.setAttribute("rx", String(n(0.24 * d.H * (1 - 0.45 * air))));
  shadow.setAttribute("ry", String(n(0.032 * d.H)));
}

/** A baton gripped across the hand, square to the forearm. */
export function drawBaton(el: SVGLineElement | null, hand: Vec, elbow: Vec, d: Dims, opacity = 1) {
  if (!el) return;
  const dx = hand.x - elbow.x;
  const dy = hand.y - elbow.y;
  const len = Math.hypot(dx, dy) || 1;
  const ux = dx / len;
  const uy = dy / len;
  const c = { x: hand.x + ux * 0.02 * d.H, y: hand.y + uy * 0.02 * d.H };
  const half = 0.1 * d.H;
  el.setAttribute("x1", String(n(c.x - uy * half)));
  el.setAttribute("y1", String(n(c.y + ux * half)));
  el.setAttribute("x2", String(n(c.x + uy * half)));
  el.setAttribute("y2", String(n(c.y - ux * half)));
  el.setAttribute("stroke-width", String(n(d.stroke * 1.2)));
  el.style.opacity = String(clamp01(opacity));
}

/** A box (or sheet) centred on `c`, `w` by `h`, turned by `angle` radians. */
export function drawRect(
  el: SVGRectElement | null,
  c: Vec,
  w: number,
  h: number,
  angle: number,
  opacity: number,
  strokeWidth: number,
) {
  if (!el) return;
  el.setAttribute("x", String(n(c.x - w / 2)));
  el.setAttribute("y", String(n(c.y - h / 2)));
  el.setAttribute("width", String(n(w)));
  el.setAttribute("height", String(n(h)));
  el.setAttribute("stroke-width", String(n(strokeWidth)));
  el.setAttribute(
    "transform",
    angle ? `rotate(${n((angle * 180) / Math.PI)} ${n(c.x)} ${n(c.y)})` : "",
  );
  el.style.opacity = String(clamp01(opacity));
}
