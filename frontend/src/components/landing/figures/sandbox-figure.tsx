"use client";

import { useEffect, useRef } from "react";

import { CARRY, STRAIN, THINK, approach, dims, mix, solve, type Pose } from "./rig";
import { FigureGlyph, drawFigure, drawRect, useStage, figure, FIGURES_ON } from "./stage";
import { knock as hit } from "./physics";
import { Particles, dust, stepParticles } from "./particles";

type Box = { kind: "load" | "new"; y: number | null; vy: number; delay: number; landed: boolean };
type Sim = { sig: string; boxes: Box[]; pose: Pose; dip: number; t: number };

const MAX_BOXES = 6;

// Studying the candidates: hand on the chin, a look down at the card, a small shrug.
const LOOK: Pose = { ...THINK, lean: 0.06, head: 0.5, shA: 0.22, elA: 0.7, shB: 0.25, elB: 0.65 };
const SHRUG: Pose = { ...THINK, lean: -0.02, head: -0.06, shA: 0.5, elA: 1.7, shB: 0.55, elB: 1.6 };

/** Never a frozen frame: the idle beat cycles every 10 s, with breathing and weight shifts. */
function pondering(t: number): Pose {
  const beat = t % 10;
  const base = beat < 4 ? THINK : beat < 6.2 ? LOOK : beat < 7.6 ? SHRUG : THINK;
  return alive(base, t, 1);
}

/** Breathing and a slow shift of weight from foot to foot, scaled by `k`. */
function alive(base: Pose, t: number, k: number): Pose {
  const breath = Math.sin(t * 2.4);
  const shift = Math.sin(t * 0.8);
  return {
    ...base,
    head: base.head + k * 0.06 * Math.sin(t * 1.3),
    lean: base.lean + k * 0.03 * shift,
    hipA: base.hipA + k * 0.1 * Math.max(0, shift),
    kneeA: base.kneeA + k * 0.2 * Math.max(0, shift),
    hipB: base.hipB + k * 0.1 * Math.max(0, -shift),
    kneeB: base.kneeB + k * 0.2 * Math.max(0, -shift),
    shA: base.shA + k * 0.04 * breath,
    shB: base.shB + k * 0.04 * breath,
  };
}
const GRAVITY = 2600;

/**
 * The cover candidate, standing on the simulator card. Nobody picked: they study the list.
 * Pick someone and the work they would take lands in their arms, one box per responsibility,
 * on top of the load they already carry. An overloaded candidate takes the strain visibly.
 */
function SandboxFigureScene({
  active,
  load,
  boxes,
  strain,
}: {
  active: boolean;
  /** Boxes already carried (existing load). */
  load: number;
  /** Responsibilities this candidate would take on. */
  boxes: number;
  strain: boolean;
}) {
  const svg = useRef<SVGSVGElement>(null);
  const rects = useRef<(SVGRectElement | null)[]>([]);
  const sim = useRef<Sim | null>(null);

  const kick = useStage(svg, (dt, w, h, still) => {
    const H = w < 640 ? 62 : 78;
    const d = dims(H);
    const ground = h - d.stroke / 2;
    const s = (sim.current ??= { sig: "", boxes: [], pose: THINK, dip: 0, t: 0 });
    s.t += dt;

    const sig = `${active}|${load}|${boxes}`;
    if (s.sig !== sig) {
      s.sig = sig;
      const kinds = active
        ? [...Array<"load">(load).fill("load"), ...Array<"new">(boxes).fill("new")]
        : [];
      s.boxes = kinds.slice(0, MAX_BOXES).map((kind, i) => ({
        kind,
        y: null,
        vy: 0,
        delay: 0.1 + i * 0.14,
        landed: false,
      }));
    }

    let target = active ? alive(strain ? STRAIN : CARRY, s.t, 0.4) : pondering(s.t);
    if (strain) target = { ...target, lean: target.lean + 0.035 * Math.sin(s.t * 4.2) };
    s.pose = still ? target : mix(s.pose, target, approach(dt, 7));
    s.dip *= Math.exp(-dt * 6);
    const p = {
      ...s.pose,
      kneeA: s.pose.kneeA + s.dip * 0.5,
      kneeB: s.pose.kneeB + s.dip * 0.45,
      hipA: s.pose.hipA + s.dip * 0.25,
      hipB: s.pose.hipB + s.dip * 0.22,
    };

    const facing = -1;
    const j = solve(p, d, w * 0.8, ground, facing);
    stepParticles(svg.current, dt);
    drawFigure(figure(svg.current, "f"), j, d, { groundY: ground });

    // the stack rides on the forearms
    const size = 0.2 * H;
    const baseX = (j.handA.x + j.handB.x) / 2 + facing * 0.03 * H;
    const baseY = Math.min(j.handA.y, j.handB.y) - d.stroke * 0.5;
    for (let i = 0; i < MAX_BOXES; i++) {
      const el = rects.current[i] ?? null;
      const b = s.boxes[i];
      if (!b) {
        drawRect(el, { x: baseX, y: baseY }, size, size, 0, 0, 1);
        continue;
      }
      const slot = baseY - (i + 0.5) * size * 1.04;
      if (still) b.landed = true;
      if (!b.landed) {
        b.delay -= dt;
        if (b.delay > 0) {
          drawRect(el, { x: baseX, y: slot }, size, size, 0, 0, 1);
          continue;
        }
        b.y ??= slot - (60 + i * 10);
        b.vy += GRAVITY * dt;
        b.y += b.vy * dt;
        if (b.y >= slot) {
          b.landed = true;
          s.dip = Math.min(1, s.dip + (strain ? 0.55 : 0.35));
          const cardEl = svg.current?.parentElement?.nextElementSibling as HTMLElement | null;
          hit(cardEl, { y: strain ? 120 : 60, r: strain ? 0.8 : 0.3 }, 0.9);
          dust(svg.current, w * 0.8, ground, 0, strain ? 0.8 : 0.45);
        }
      }
      const y = b.landed ? slot : (b.y ?? slot);
      const sway = strain ? Math.sin(s.t * 4.2 + i * 0.6) * i : 0;
      el?.setAttribute("class", b.kind === "load" ? "fig-box fig-box-load" : "fig-box");
      drawRect(el, { x: baseX + sway * 0.025 * H, y }, size, size, sway * 0.035, 1, d.stroke * 0.7);
    }
  });

  useEffect(() => kick(), [kick, active, load, boxes, strain]);

  return (
    <div aria-hidden className="relative h-24">
      <svg
        ref={svg}
        className="pointer-events-none absolute inset-0 h-full w-full overflow-visible"
      >
        <FigureGlyph name="f" />
        <Particles />
        {Array.from({ length: MAX_BOXES }, (_, i) => (
          <rect
            key={i}
            ref={(el) => {
              rects.current[i] = el;
            }}
            rx={2}
            className="fig-box"
          />
        ))}
      </svg>
    </div>
  );
}

export function SandboxFigure(props: Parameters<typeof SandboxFigureScene>[0]) {
  return FIGURES_ON ? <SandboxFigureScene {...props} /> : null;
}
