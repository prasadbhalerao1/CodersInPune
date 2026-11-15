"use client";

import { useEffect, useRef } from "react";

import { CARRY, STRAIN, THINK, approach, dims, mix, solve, type Pose } from "./rig";
import { FigureGlyph, drawFigure, drawRect, useStage, figure, FIGURES_ON } from "./stage";
import { knock as hit } from "./physics";
import { Particles, dust, stepParticles } from "./particles";

type Box = { kind: "load" | "new"; y: number | null; vy: number; delay: number; landed: boolean };
type Sim = { sig: string; boxes: Box[]; pose: Pose; dip: number; t: number };

const MAX_BOXES = 6;
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

    let target = active ? (strain ? STRAIN : CARRY) : THINK;
    target = {
      ...target,
      head: target.head + (active ? 0 : 0.05 * Math.sin(s.t * 1.3)),
      lean: target.lean + 0.01 * Math.sin(s.t * 2) + (strain ? 0.035 * Math.sin(s.t * 4.2) : 0),
    };
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
