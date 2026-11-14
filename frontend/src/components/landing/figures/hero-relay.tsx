"use client";

import { useRef } from "react";

import {
  READY,
  STAND,
  clamp01,
  dims,
  gait,
  mix,
  runLift,
  smooth,
  solve,
  stride,
  vlerp,
  wave,
  type Dims,
  type Joints,
  type Pose,
} from "./rig";
import { FigureGlyph, drawBaton, drawFigure, useStage, figure, FIGURES_ON } from "./stage";

type Runner = { x: number; v: number; ph: number; op: number };
type Sim = {
  w: number;
  a: Runner;
  b: Runner;
  stage: "approach" | "exchange" | "after" | "fade";
  t: number;
  handoff: number;
  wave: number;
  clock: number;
};

const sizeFor = (w: number) => (w < 640 ? 40 : w < 1024 ? 50 : 60);

/**
 * "Pass the accountability", acted out along the top edge of the hero's bottom bar: a runner
 * brings the baton in, the next one accelerates out of the exchange zone reaching back, the
 * baton changes hands at speed, and the first runner slows and waves them on. Then the next leg.
 */
function HeroRelayScene() {
  const svg = useRef<SVGSVGElement>(null);
  const baton = useRef<SVGLineElement>(null);
  const sim = useRef<Sim | null>(null);

  useStage(svg, (dt, w, h, still) => {
    const H = sizeFor(w);
    const d = dims(H);
    const V = 3.3 * H;
    const ground = h - d.stroke / 2;

    const fresh = (): Sim => ({
      w,
      a: { x: -0.04 * w - H, v: V, ph: 0, op: 1 },
      b: { x: 0.5 * w, v: 0, ph: 0, op: 0 },
      stage: "approach",
      t: 0,
      handoff: 0,
      wave: 0,
      clock: 0,
    });
    let s = sim.current;
    if (!s || Math.abs(s.w - w) > 40) s = sim.current = fresh();

    const runNorm = (r: Runner) => clamp01(r.v / V);
    const step = (r: Runner, target: number, accel: number) => {
      r.v = r.v < target ? Math.min(target, r.v + accel * dt) : Math.max(target, r.v - accel * dt);
      r.x += r.v * dt;
      r.ph += (2 * Math.PI * r.v * dt) / stride(runNorm(r), H);
    };

    if (still) {
      // reduced motion: the moment of the exchange, held
      s.a = { x: 0.5 * w, v: 0.86 * V, ph: 1.1, op: 1 };
      s.b = { x: 0.5 * w + 0.48 * H, v: 0.86 * V, ph: 1.1 + Math.PI * 0.6, op: 1 };
      s.stage = "exchange";
      s.handoff = 0.5;
    } else {
      s.clock += dt;
      s.t += dt;
      s.b.op = Math.min(1, s.b.op + dt * 2);
      if (s.stage === "approach") {
        step(s.a, V, V);
        const gap = s.b.x - s.a.x;
        if (gap < 1.95 * H) step(s.b, 0.86 * V, 1.1 * V);
        if (gap < 0.48 * H) {
          s.stage = "exchange";
          s.t = 0;
        }
      } else if (s.stage === "exchange") {
        step(s.b, 0.86 * V, V);
        step(s.a, s.b.v, 3 * V);
        s.handoff = clamp01(s.t / 0.45);
        if (s.t > 0.55) {
          s.stage = "after";
          s.t = 0;
        }
      } else if (s.stage === "after") {
        step(s.b, 1.08 * V, 0.8 * V);
        step(s.a, 0, V / 1.2);
        if (s.a.v === 0) s.wave += dt;
        if (s.b.x > w + 2 * H && s.wave > 1.9) {
          s.stage = "fade";
          s.t = 0;
        }
      } else {
        s.wave += dt;
        s.a.op = Math.max(0, s.a.op - dt * 1.6);
        if (s.a.op === 0) s = sim.current = fresh();
      }
    }

    const running = (r: Runner): Pose => {
      const k = runNorm(r);
      return mix(STAND, gait(r.ph, smooth(Math.min(1, k * 1.15))), smooth(k / 0.22));
    };

    // runner A: in, through the exchange, then easing off into a wave
    let pa = running(s.a);
    if (s.wave > 0) pa = mix(pa, wave(s.wave), smooth(s.wave / 0.35));

    // runner B: set in the zone, then accelerating with the far hand back until it has the baton
    const kb = runNorm(s.b);
    const breathe = { ...READY, lean: READY.lean + 0.02 * Math.sin(s.clock * 3) };
    let pb = mix(breathe, running(s.b), smooth(kb * 1.4));
    const holding = s.stage === "after" || s.stage === "fade";
    if (!holding) pb = { ...pb, shB: -1.05, elB: 0.12 };

    const liftA = runLift(s.a.ph, runNorm(s.a), H);
    const liftB = runLift(s.b.ph, kb, H);
    let ja = solve(pa, d, s.a.x, ground, 1, { lift: liftA });
    let jb = solve(pb, d, s.b.x, ground, 1, { lift: liftB });

    if (s.stage === "exchange") {
      // both hands meet between the runners, a little below the chest
      const reachW = smooth(Math.min(s.handoff * 3, (1 - s.handoff) * 3 + 0.4));
      const target = {
        x: (ja.chest.x + jb.chest.x) / 2,
        y: (ja.chest.y + jb.chest.y) / 2 + 0.2 * H,
      };
      ja = solve(pa, d, s.a.x, ground, 1, { lift: liftA, reachA: { target, w: reachW } });
      jb = solve(pb, d, s.b.x, ground, 1, {
        lift: liftB,
        reachB: { target, w: Math.max(reachW, 0.6), bend: -1 },
      });
    }

    drawFigure(figure(svg.current, "a"), ja, d, { opacity: s.a.op, groundY: ground });
    drawFigure(figure(svg.current, "b"), jb, d, { opacity: s.b.op, groundY: ground });
    placeBaton(baton.current, s, ja, jb, d);
  });

  return (
    <svg
      ref={svg}
      aria-hidden
      className="pointer-events-none absolute inset-x-0 bottom-full h-24 w-full overflow-visible"
    >
      <FigureGlyph name="a" />
      <FigureGlyph name="b" />
      <line ref={baton} className="fig-baton" />
    </svg>
  );
}

function placeBaton(el: SVGLineElement | null, s: Sim, ja: Joints, jb: Joints, d: Dims) {
  if (s.stage === "exchange") {
    const k = smooth((s.handoff - 0.35) / 0.4);
    drawBaton(el, vlerp(ja.handA, jb.handB, k), vlerp(ja.elbowA, jb.elbowB, k), d);
  } else if (s.stage === "approach") {
    drawBaton(el, ja.handA, ja.elbowA, d);
  } else {
    drawBaton(el, jb.handB, jb.elbowB, d);
  }
}

export function HeroRelay() {
  return FIGURES_ON ? <HeroRelayScene /> : null;
}
