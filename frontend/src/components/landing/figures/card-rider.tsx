"use client";

import { useRef } from "react";

import { STAND, approach, clamp01, dims, gait, mix, smooth, solve, stride, type Pose } from "./rig";
import { wave } from "./gestures";
import { FigureGlyph, FIGURES_ON, drawFigure, figure, useStage } from "./stage";
import { knock as hit } from "./physics";
import { Particles, dust, sparks, stepParticles } from "./particles";

type Stage = "wait" | "run" | "leap" | "hang" | "climb" | "wave" | "fade";
type Sim = {
  stage: Stage;
  t: number;
  x: number;
  ph: number;
  op: number;
  theta: number; // swing angle of the hanging body
  omega: number; // its angular velocity
  brace: number; // 1 right after a scroll reversal, decays
  lastY: number | null;
  v: number;
  pose: Pose;
};

const HANG: Pose = {
  ...STAND,
  lean: 0,
  head: -0.2,
  hipA: 0.3,
  kneeA: 0.7,
  hipB: 0.05,
  kneeB: 0.25,
  shA: 2.75,
  elA: 0.1,
  shB: 2.85,
  elB: 0.08,
};

/**
 * The signature scene. The section pins its text and scrolls the card past it, so the card is
 * what moves: a figure runs in from the left edge of the viewport, leaps for the card's corner,
 * and hangs from it while the user scrolls. The body is a damped pendulum driven by scroll
 * velocity, so it swings out on a fast scroll and braces when the scroll reverses. When the card
 * is nearly gone the figure pulls itself up, waves, and fades.
 *
 * Anchoring: the stage is the card's sibling, so the ledge is always at (stage right, 0). The
 * card's document position is read once per resize; per frame only `scrollY` is read.
 */
function CardRiderScene() {
  const svg = useRef<SVGSVGElement>(null);
  const sim = useRef<Sim | null>(null);
  const card = useRef<{ top: number; h: number; left: number } | null>(null);

  useStage(svg, (dt, w, h, still) => {
    const el = svg.current;
    if (!el) return;
    const H = 78;
    const d = dims(H);
    const s = (sim.current ??= {
      stage: "wait",
      t: 0,
      x: 0,
      ph: 0,
      op: 0,
      theta: 0,
      omega: 0,
      brace: 0,
      lastY: null,
      v: 0,
      pose: STAND,
    });
    // the card's document box, refreshed whenever the stage is measured (dt === 0 on a resize)
    if (!card.current || dt === 0) {
      const r = el.parentElement?.getBoundingClientRect();
      if (r) card.current = { top: r.top + window.scrollY, h: r.height, left: r.left };
    }
    const c = card.current;
    if (!c) return;

    const y = window.scrollY;
    const vh = window.innerHeight;
    const cardTop = c.top - y; // viewport y of the ledge
    const v = s.lastY === null || dt === 0 ? 0 : (y - s.lastY) / dt;
    if (dt > 0) s.lastY = y;
    if (Math.sign(v) !== Math.sign(s.v) && Math.abs(v) > 160 && Math.abs(s.v) > 160) {
      s.brace = 1;
    }
    s.v += (v - s.v) * approach(dt, 12);
    s.brace *= Math.exp(-dt * 3.5);
    s.t += dt;

    // the stage's left edge is the card's left edge and its bottom edge is the card's top: the
    // ledge is the card's top-left corner, the run-up is along the card's top edge, and the figure
    // enters from the right edge of the viewport, where only petals live
    const ledge = { x: 0.04 * H, y: h };
    const startX = window.innerWidth - c.left + 0.5 * H;

    if (still) {
      s.stage = "hang";
      s.op = 1;
      s.theta = 0.12;
    } else if (s.stage === "wait") {
      s.op = 0;
      if (cardTop < vh * 0.92 && cardTop + c.h > vh * 0.5) {
        s.stage = "run";
        s.t = 0;
        s.x = startX;
        s.ph = 0;
      }
    } else if (s.stage === "run") {
      s.op = Math.min(1, s.op + dt * 3);
      const speed = 6.4 * H;
      s.x -= speed * dt;
      s.ph += (2 * Math.PI * speed * dt) / stride(1, H);
      if (s.x < ledge.x + 1.1 * H) {
        s.stage = "leap";
        s.t = 0;
      }
    } else if (s.stage === "leap") {
      const k = clamp01(s.t / 0.34);
      s.x = ledge.x + 1.1 * H - k * 1.25 * H; // past the corner, then the hands catch it
      if (k >= 1) {
        s.stage = "hang";
        s.t = 0;
        s.omega = 2.2;
        // the whole card takes the catch
        hit(el.parentElement, { y: 210, r: -2.4 }, 0.8);
        sparks(el, ledge.x, ledge.y, -Math.PI / 2, 2.2, 0.8);
      }
    } else if (s.stage === "hang") {
      // card almost scrolled away upwards: get off. Scrolled back above the start: reset.
      if (cardTop < 210 || cardTop + c.h < vh * 0.42) {
        s.stage = "climb";
        s.t = 0;
      } else if (cardTop > vh * 1.05) {
        s.stage = "fade";
        s.t = 0;
      }
    } else if (s.stage === "climb") {
      if (s.t > 0.55) {
        s.stage = "wave";
        s.t = 0;
      }
    } else if (s.stage === "wave") {
      if (s.t > 1.7) {
        s.stage = "fade";
        s.t = 0;
      }
    } else {
      s.op = Math.max(0, s.op - dt * 2);
      if (s.op === 0 && cardTop > vh) {
        s.stage = "wait";
        s.theta = 0;
        s.omega = 0;
      }
    }

    // pendulum: scroll velocity pushes the body back (page moves up ⇒ body trails downwards-left)
    const target = Math.max(-0.7, Math.min(0.7, s.v / 2200));
    const omega0 = 6.5;
    const zeta = 0.32;
    s.omega += (omega0 * omega0 * (target - s.theta) - 2 * zeta * omega0 * s.omega) * dt;
    s.theta += s.omega * dt;

    let j;
    if (s.stage === "run" || s.stage === "leap") {
      const leapK = s.stage === "leap" ? clamp01(s.t / 0.34) : 0;
      const run = gait(s.ph, 1);
      // off the corner: the arms come down to catch the ledge, the legs tuck, then the body drops
      const catchPose: Pose = {
        ...run,
        shA: 0.9,
        elA: 0.1,
        shB: 0.7,
        elB: 0.1,
        hipA: 0.5,
        kneeA: 1.2,
        hipB: 0.2,
        kneeB: 0.8,
        lean: -0.15,
        head: 0.2,
      };
      s.pose = mix(run, catchPose, smooth(leapK));
      const hop = Math.sin(Math.min(1, leapK * 1.6) * Math.PI) * 0.35 * H;
      const fall = smooth((leapK - 0.45) / 0.55) * H; // dropping past the corner
      j = solve(s.pose, d, s.x, ledge.y + fall, -1, { lift: hop });
    } else if (s.stage === "hang") {
      const swing = s.theta;
      const dangle = Math.max(-0.5, Math.min(0.5, s.omega * 0.12));
      const p: Pose = {
        ...HANG,
        lean: -swing * 0.35,
        head: -0.25 + swing * 0.2,
        hipA: HANG.hipA - dangle + s.brace * 0.65,
        hipB: HANG.hipB - dangle * 0.8 + s.brace * 0.5,
        kneeA: HANG.kneeA + Math.abs(dangle) * 0.6 + s.brace * 1.1,
        kneeB: HANG.kneeB + Math.abs(dangle) * 0.5 + s.brace * 0.9,
      };
      s.pose = mix(s.pose, p, approach(dt, 14));
      const armLen = (d.upper + d.fore) * 0.94;
      const chest = {
        x: ledge.x - 0.3 * H + Math.sin(swing) * armLen,
        y: ledge.y + Math.cos(swing) * armLen,
      };
      const pelvisY = chest.y + Math.cos(s.pose.lean) * d.torso;
      const pelvisX = chest.x - Math.sin(s.pose.lean) * d.torso;
      const grip = (dx: number) => ({ target: { x: ledge.x + dx, y: ledge.y }, w: 1, bend: -1 });
      j = solve(s.pose, d, pelvisX, 0, 1, {
        pelvisY,
        reachA: grip(0.12 * H),
        reachB: grip(0.02 * H),
      });
    } else {
      // climbing onto the ledge, then standing on it waving
      const k = s.stage === "climb" ? smooth(s.t / 0.55) : 1;
      if (s.stage === "wave" && s.t === dt) dust(el, ledge.x + 0.5 * H, ledge.y, 0, 0.7);
      const up: Pose =
        s.stage === "wave"
          ? wave(s.t)
          : { ...STAND, shA: 1.9, elA: 1.2, shB: 1.6, elB: 1.3, hipA: 1.2, kneeA: 1.6, lean: 0.3 };
      s.pose = mix(s.pose, up, approach(dt, 10));
      const standX = ledge.x + 0.5 * H;
      const x = ledge.x - 0.2 * H + k * (standX - (ledge.x - 0.2 * H));
      j = solve(s.pose, d, x, ledge.y, 1, { lift: (1 - k) * -0.9 * H });
    }
    stepParticles(el, dt);
    drawFigure(figure(el, "r"), j, d, { opacity: s.op });
    el.dataset.stage = s.stage;
  });

  return (
    <svg
      ref={svg}
      aria-hidden
      className="pointer-events-none absolute bottom-full left-0 hidden h-[5.5rem] w-[100vw] overflow-visible lg:block"
    >
      <FigureGlyph name="r" />
      <Particles />
    </svg>
  );
}

export function CardRider() {
  return FIGURES_ON ? <CardRiderScene /> : null;
}
