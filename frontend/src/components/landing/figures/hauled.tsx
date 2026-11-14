"use client";

import { useRef, type ReactNode } from "react";

import { STAND, approach, clamp01, dims, mix, solve, type Pose, type Vec } from "./rig";
import { haul } from "./gestures";
import { FigureGlyph, FIGURES_ON, drawFigure, figure, useStage } from "./stage";
import { Body, Spring, feel, knock as hit } from "./physics";
import { Particles, dust, sparks, stepParticles } from "./particles";

const HAULS = 5;
const DROP = 120; // px the card starts below its place

const PULL: Pose = {
  ...STAND,
  lean: -0.42,
  head: 0.35,
  hipA: 0.6,
  kneeA: 0.3,
  hipB: -0.5,
  kneeB: 0.12,
  shA: 1.4,
  elA: 0.6,
  shB: 1.1,
  elB: 0.7,
};

type Sim = {
  top: number;
  pose: Pose;
  ph: number;
  ty: number;
  rope: number;
  spring: Spring;
  body: Body;
  home: boolean;
};

/**
 * A card that is hauled into place rather than fading in. A figure stands where the card's top
 * edge will be, leaning back on a rope tied to the card's corner, and pulls it up hand over hand
 * as the card enters the viewport. The progress is the scroll position, so scrolling back lets
 * the card slide down again and the figure gets dragged with it. The card itself only receives
 * a transform; its layout is untouched.
 */
function HauledScene({ children, className }: { children: ReactNode; className?: string }) {
  const svg = useRef<SVGSVGElement>(null);
  const box = useRef<HTMLDivElement>(null);
  const rope = useRef<SVGPathElement>(null);
  const sim = useRef<Sim | null>(null);

  useStage(svg, (dt, w, h, still) => {
    const el = svg.current;
    const card = box.current;
    if (!el || !card) return;
    const H = 80;
    const d = dims(H);
    const s = (sim.current ??= {
      top: 0,
      pose: STAND,
      ph: 0,
      ty: 0,
      rope: 1,
      spring: new Spring(230, 11),
      body: new Body(),
      home: false,
    });
    stepParticles(el, dt);
    if (dt === 0 || !s.top) {
      // the card's resting document position (its current transform taken back out)
      s.top = card.getBoundingClientRect().top + window.scrollY - s.ty;
    }
    const vh = window.innerHeight;
    const top = s.top - window.scrollY;
    const p = still ? 1 : clamp01((vh * 0.92 - top) / (vh * 0.42));
    // hauls: each one is a keyed cycle (reach, grip, drive back, recover); the card comes up
    // only while the rope is being drawn in, so it moves in jerks, in time with the body
    const k = Math.min(HAULS - 1e-6, p * HAULS);
    const step = Math.floor(k);
    const cycle = haul(k - step);
    const pe = p >= 1 ? 1 : (step + cycle.draw) / HAULS;
    // the card is heavy: it chases the rope on a spring, overshooting each haul a little
    const want = (1 - pe) * DROP;
    if (still) {
      s.spring.x = want;
      s.spring.v = 0;
    } else s.spring.step(dt, want);
    s.ty = s.spring.x;
    card.style.transform = Math.abs(s.ty) > 0.5 ? `translate3d(0, ${s.ty.toFixed(1)}px, 0)` : "";

    const ground = h - d.stroke / 2;
    const done = p >= 1;
    const corner: Vec = { x: w - 0.08 * H, y: h + s.ty + d.stroke };
    const homeX = Math.max(1.6 * H, 0.42 * w);
    // home: the card clunks into place and the hauler, suddenly pulling on nothing, staggers back
    if (done && !s.home && !still) {
      s.home = true;
      hit(card, { y: -260, r: 1.4 }, 0.8);
      s.body.vx = -3.2 * H;
      dust(el, homeX, h - d.stroke / 2, -1, 1);
      sparks(el, w - 0.08 * H, h, -Math.PI / 2, 1.6, 0.7);
    }
    if (!done) s.home = false;
    if (!s.body.x) s.body.x = homeX;
    s.body.step(dt);
    if (s.body.grounded) s.body.seek(homeX, 1.4 * H, 6 * H, dt);
    const x = s.body.x;
    const target = done ? STAND : still ? PULL : cycle.pose;
    s.pose = still ? target : mix(s.pose, target, approach(dt, done ? 6 : 18));
    s.rope += ((done ? 0 : 1) - s.rope) * (still ? 1 : approach(dt, 6));

    // hands alternate along the rope: hand over hand, in time with the hauls
    const chestGuess = { x: x - Math.sin(0.42) * d.torso, y: ground - 0.5 * H - 0.3 * H };
    const along = (t: number): Vec => ({
      x: chestGuess.x + (corner.x - chestGuess.x) * t,
      y: chestGuess.y + (corner.y - chestGuess.y) * t,
    });
    // the lead hand reaches up the rope for the grip, the trailing hand holds closer in
    const reachLen =
      (d.upper + d.fore) / Math.hypot(corner.x - chestGuess.x, corner.y - chestGuess.y);
    const a = reachLen * 0.88 * cycle.reach;
    const b = reachLen * 0.5;
    const j = solve(feel(s.pose, s.body, H, 1), d, x, ground, 1, {
      reachA: done ? undefined : { target: along(a), w: s.rope, bend: -1 },
      reachB: done ? undefined : { target: along(b), w: s.rope, bend: -1 },
    });
    drawFigure(figure(el, "h"), j, d, { groundY: ground });
    const r = rope.current;
    if (r) {
      const far = j.handA.x < j.handB.x ? j.handA : j.handB;
      const near = far === j.handA ? j.handB : j.handA;
      r.setAttribute(
        "d",
        `M${far.x.toFixed(1)} ${far.y.toFixed(1)}L${near.x.toFixed(1)} ${near.y.toFixed(1)}L${corner.x.toFixed(1)} ${corner.y.toFixed(1)}`,
      );
      r.setAttribute("stroke-width", (d.stroke * 0.55).toFixed(1));
      r.style.opacity = String(s.rope);
    }
  });

  return (
    <div className={className ? `relative ${className}` : "relative"}>
      <svg
        ref={svg}
        aria-hidden
        className="pointer-events-none absolute bottom-full left-0 hidden h-24 w-full overflow-visible md:block"
      >
        <path ref={rope} className="fig-rope" />
        <FigureGlyph name="h" />
        <Particles />
      </svg>
      <div ref={box} style={{ willChange: "transform" }}>
        {children}
      </div>
    </div>
  );
}

export function Hauled(props: { children: ReactNode; className?: string }) {
  return FIGURES_ON ? (
    <HauledScene {...props} />
  ) : (
    <div className={props.className}>{props.children}</div>
  );
}
