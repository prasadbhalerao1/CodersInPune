"use client";

import { useEffect, useRef } from "react";

import { approach, dims, mix, sit, solve, type Pose, type Vec } from "./rig";
import { STOMP_TIME, cheer, stamping, stomp } from "./gestures";
import { FigureGlyph, FIGURES_ON, drawFigure, drawRect, figure, useStage } from "./stage";

type Box = { x: number; y: number; w: number; h: number };
type State = "sit" | "stomp" | "cheer";
type Sim = {
  t: number;
  st: State;
  stt: number;
  btn: Box | null;
  pose: Pose;
  pointer: Vec | null;
  hover: boolean;
  left: number;
  top: number;
};

const HOLD_UP: Partial<Pose> = { shA: 2.95, elA: 0.05 };

/**
 * Someone sitting on the end of the final call-to-action button, holding up a sign with an arrow
 * pointing at it. When the pointer comes near they stand up and stamp on the button (which
 * dips); when it hovers the button they cheer.
 */
function SignHolderScene() {
  const svg = useRef<SVGSVGElement>(null);
  const board = useRef<SVGRectElement>(null);
  const arrow = useRef<SVGPathElement>(null);
  const sim = useRef<Sim | null>(null);

  useStage(svg, (dt, w, _h, still) => {
    const el = svg.current;
    const btn = el?.parentElement?.querySelector<HTMLElement>('[data-fig="try-cta"]');
    if (!el || !btn) return;
    const H = 58;
    const d = dims(H);
    const s = (sim.current ??= {
      t: 0,
      st: "sit",
      stt: 0,
      btn: null,
      pose: sit(0),
      pointer: null,
      hover: false,
      left: 0,
      top: 0,
    });
    s.t += dt;
    s.stt += dt;
    if (dt === 0 || !s.btn) {
      const sr = el.getBoundingClientRect();
      const b = btn.getBoundingClientRect();
      s.left = sr.left;
      s.top = sr.top + window.scrollY;
      s.btn = { x: b.left - sr.left, y: b.top - sr.top, w: b.width, h: b.height };
    }
    const b = s.btn!;
    const near =
      !!s.pointer && Math.hypot(s.pointer.x - (b.x + b.w), s.pointer.y - (b.y + b.h / 2)) < 4.5 * H;

    if (!still) {
      const go = (st: State) => {
        s.st = st;
        s.stt = 0;
      };
      if (s.st === "sit" && s.hover) go("cheer");
      else if (s.st === "sit" && near) go("stomp");
      else if (s.st === "stomp" && (s.stt > STOMP_TIME || s.hover)) go(s.hover ? "cheer" : "sit");
      else if (s.st === "cheer" && !s.hover && s.stt > 0.6) go("sit");
    }

    const ledge: Vec = { x: b.x + b.w - 0.55 * H, y: b.y + d.stroke * 0.4 };
    let j;
    let dip = 0;
    if (s.st === "sit") {
      const p = { ...sit(still ? 0 : s.t), ...HOLD_UP, lean: -0.05 };
      s.pose = still ? p : mix(s.pose, p, approach(dt, 8));
      j = solve(s.pose, d, ledge.x, ledge.y, 1, { pelvisY: ledge.y - d.stroke * 0.6 });
    } else if (s.st === "stomp") {
      // up on the feet, three keyed stamps; the button dips as each one lands
      const p: Pose = { ...stomp(s.stt), ...HOLD_UP };
      s.pose = mix(s.pose, p, approach(dt, 20));
      dip = stamping(s.stt) ? 3 : 0;
      j = solve(s.pose, d, ledge.x + 0.1 * H, ledge.y, 1);
    } else {
      const ch = cheer(s.stt);
      s.pose = mix(s.pose, { ...ch.pose, ...HOLD_UP }, approach(dt, 16));
      j = solve(s.pose, d, ledge.x + 0.1 * H, ledge.y, 1, { lift: ch.lift * H });
    }
    btn.style.transform = dip ? `translate3d(0, ${dip}px, 0)` : "";
    drawFigure(figure(el, "s"), j, d, { groundY: s.st === "sit" ? undefined : ledge.y });

    // the sign: a board above the raised hand, an arrow pointing down at the button
    const c: Vec = { x: j.handA.x, y: j.handA.y - 0.2 * H };
    const bw = 0.5 * H;
    const bh = 0.34 * H;
    drawRect(board.current, c, bw, bh, 0.04 * Math.sin(s.t * 1.7), 1, d.stroke * 0.6);
    const a = arrow.current;
    if (a) {
      const top = c.y - bh * 0.3;
      const bot = c.y + bh * 0.3;
      a.setAttribute(
        "d",
        `M${c.x.toFixed(1)} ${top.toFixed(1)}L${c.x.toFixed(1)} ${bot.toFixed(1)}M${(c.x - 0.09 * H).toFixed(1)} ${(bot - 0.09 * H).toFixed(1)}L${c.x.toFixed(1)} ${bot.toFixed(1)}L${(c.x + 0.09 * H).toFixed(1)} ${(bot - 0.09 * H).toFixed(1)}`,
      );
      a.setAttribute("stroke-width", (d.stroke * 0.7).toFixed(1));
    }
    void w;
  });

  useEffect(() => {
    const onMove = (e: PointerEvent) => {
      const s = sim.current;
      if (!s?.btn) return;
      s.pointer = { x: e.clientX - s.left, y: e.clientY + window.scrollY - s.top };
      const b = s.btn;
      s.hover =
        s.pointer.x >= b.x &&
        s.pointer.x <= b.x + b.w &&
        s.pointer.y >= b.y &&
        s.pointer.y <= b.y + b.h;
    };
    window.addEventListener("pointermove", onMove, { passive: true });
    return () => window.removeEventListener("pointermove", onMove);
  }, []);

  return (
    <svg
      ref={svg}
      aria-hidden
      className="pointer-events-none absolute inset-0 hidden h-full w-full overflow-visible md:block"
    >
      <FigureGlyph name="s" />
      <rect ref={board} rx={1.5} className="fig-doc" />
      <path ref={arrow} className="fig fig-arrow" />
    </svg>
  );
}

export function SignHolder() {
  return FIGURES_ON ? <SignHolderScene /> : null;
}
