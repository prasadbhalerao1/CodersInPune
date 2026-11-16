"use client";

import { useEffect, useRef } from "react";

import {
  STAND,
  approach,
  clamp01,
  dims,
  gait,
  mix,
  smooth,
  solve,
  stride,
  type Pose,
  type Vec,
} from "./rig";
import { BECKON_TIME, KNOCK_TIME, SHOVE_TIME, beckon, cheer, knock, shove, wave } from "./gestures";
import { FigureGlyph, FIGURES_ON, drawFigure, figure, useStage } from "./stage";
import { Body, crouch, feel, knock as hit } from "./physics";
import { Particles, dust, sparks, stepParticles } from "./particles";

type Box = { x: number; y: number; w: number; h: number };
type Greet = "walk" | "wave" | "point" | "shove" | "idle" | "flinch" | "cheer" | "beckon" | "knock";
type Sim = {
  t: number;
  cta: Box | null;
  card: Box | null;
  stageTop: number;
  stageLeft: number;
  measuredAt: number;
  tx: Vec; // the card's current carry offset
  carry: number; // 0..1 the card is being carried in
  setDown: number; // 0..1 the card has been set down
  a: { x: number; f: number; ph: number; pose: Pose };
  b: { x: number; f: number; ph: number; pose: Pose };
  greet: Greet;
  gt: number;
  shove: number;
  idleSince: number;
  ab: Body;
  bb: Body;
  landed: boolean;
  setDownHit: boolean;
  skid: number;
  pointer: Vec | null;
  hover: boolean;
};

const CARRY_UP: Pose = { ...STAND, shA: 2.9, elA: 0.08, shB: 2.95, elB: 0.06, head: -0.1 };
const SQUAT: Pose = { ...CARRY_UP, hipA: 0.7, kneeA: 1.1, hipB: 0.5, kneeB: 0.9, lean: 0.15 };
const LEAN_ON: Pose = {
  ...STAND,
  lean: -0.12,
  head: 0.08,
  hipA: 0.08,
  kneeA: 0.05,
  hipB: 0.32,
  kneeB: 0.42,
  shA: 1.5,
  elA: 1.6,
  shB: -0.2,
  elB: 0.3,
};
const FRONT: Pose = {
  ...STAND,
  lean: 0,
  hipA: 0.14,
  kneeA: 0.04,
  hipB: 0.14,
  kneeB: 0.04,
  shA: 0.3,
  elA: 0.25,
  shB: 0.3,
  elB: 0.25,
};
/**
 * Standing about between gestures: breathing, a slow weight shift from foot to foot, the odd
 * glance around. Never a frozen frame, so the figure reads as waiting, not stuck.
 */
function idling(t: number): Pose {
  const breath = Math.sin(t * 2.4);
  const shift = Math.sin(t * 0.8);
  const glance = Math.sin(t * 0.55) * Math.sin(t * 1.3);
  return {
    ...FRONT,
    lean: 0.05 * shift,
    head: 0.22 * glance + 0.03 * breath,
    hipA: FRONT.hipA + 0.12 * Math.max(0, shift),
    kneeA: FRONT.kneeA + 0.24 * Math.max(0, shift),
    hipB: FRONT.hipB + 0.12 * Math.max(0, -shift),
    kneeB: FRONT.kneeB + 0.24 * Math.max(0, -shift),
    shA: FRONT.shA + 0.08 * breath,
    shB: FRONT.shB + 0.08 * breath,
    elA: FRONT.elA + 0.14 * shift,
    elB: FRONT.elB - 0.14 * shift,
  };
}

const STARTLE: Pose = {
  ...FRONT,
  lean: -0.2,
  head: -0.15,
  shA: 2.3,
  elA: 0.5,
  shB: 2.3,
  elB: 0.5,
  hipA: 0.35,
  kneeA: 0.4,
  hipB: 0.35,
  kneeB: 0.4,
};

/**
 * The hero's crew, and the one scene that talks to the viewer. Two figures carry the readout
 * card in from the right and set it down; one stays and leans on it. The other walks to the
 * simulator button, turns to face the viewer, waves, points at the button and shoves it (the
 * real button moves). From then on its head follows the pointer; it flinches when the pointer
 * comes close, cheers when the button is hovered, beckons when the viewer idles, and knocks on
 * the glass when they still have not moved.
 */
function HeroCrewScene() {
  const svg = useRef<SVGSVGElement>(null);
  const sim = useRef<Sim | null>(null);

  useStage(svg, (dt, w, h, still) => {
    const el = svg.current;
    if (!el) return;
    const H = w < 1280 ? 72 : 86;
    const d = dims(H);
    const s = (sim.current ??= {
      t: 0,
      cta: null,
      card: null,
      stageTop: 0,
      stageLeft: 0,
      measuredAt: -1,
      tx: { x: 0, y: 0 },
      carry: 0,
      setDown: 0,
      a: { x: 0, f: -1, ph: 0, pose: CARRY_UP },
      b: { x: 0, f: -1, ph: 0, pose: CARRY_UP },
      greet: "walk",
      gt: 0,
      shove: 0,
      idleSince: 0,
      ab: new Body(),
      bb: new Body(),
      landed: false,
      setDownHit: false,
      skid: 0,
      pointer: null,
      hover: false,
    });
    s.t += dt;
    stepParticles(el, dt);
    s.bb.step(dt);
    const cardEl = document.querySelector<HTMLElement>('[data-fig="readout"]');
    const ctaEl = document.querySelector<HTMLElement>('[data-fig="cta"]');
    if (!cardEl || !ctaEl) return;

    // the hero's entrance moves things for ~1.5 s, so measure a few times early, then on resize
    if (dt === 0 || s.measuredAt < 0 || (s.t < 2.2 && s.t - s.measuredAt > 0.4)) {
      const sr = el.getBoundingClientRect();
      s.stageTop = sr.top + window.scrollY;
      s.stageLeft = sr.left;
      const c = cardEl.getBoundingClientRect();
      s.card = {
        x: c.left - sr.left - s.tx.x,
        y: c.top - sr.top - s.tx.y,
        w: c.width,
        h: c.height,
      };
      const b = ctaEl.getBoundingClientRect();
      s.cta = { x: b.left - sr.left, y: b.top - sr.top, w: b.width, h: b.height };
      s.measuredAt = s.t;
    }
    const card = s.card;
    const cta = s.cta;
    if (!card || !cta) return;

    // ── the card comes in on two pairs of hands ──
    const carryT = still ? 10 : s.t;
    const inK = smooth(clamp01((carryT - 0.3) / 2.3));
    const downK = smooth(clamp01((carryT - 2.7) / 0.45));
    const fromX = w - card.x + 0.4 * H;
    const bob = (1 - downK) * 0.04 * H * Math.sin(carryT * 9);
    const lift = (1 - downK) * -0.92 * H;
    const tx = { x: (1 - inK) * fromX, y: lift + bob };
    s.tx = tx;
    cardEl.style.transform =
      Math.abs(tx.x) > 0.5 || Math.abs(tx.y) > 0.5
        ? `translate3d(${tx.x.toFixed(1)}px, ${tx.y.toFixed(1)}px, 0)`
        : "";
    cardEl.style.willChange = downK < 1 ? "transform" : "";

    const groundCard = card.y + card.h + d.stroke * 0.5; // the card's resting bottom edge
    if (downK >= 1 && !s.setDownHit && !still) {
      s.setDownHit = true;
      hit(cardEl, { y: 420, r: 9 }, 0.75);
      s.ab.squash.kick(5);
      s.bb.squash.kick(5);
      dust(el, card.x - 0.2 * H, groundCard, -1, 0.9);
      dust(el, card.x + card.w + 0.2 * H, groundCard, 1, 0.9);
    }
    const carrying = downK < 1;
    const walking = inK < 1;

    // B carries the back end and then leans on the card
    const bx = card.x + card.w + tx.x + 0.22 * H;
    if (carrying) {
      s.b.x = bx;
      s.b.ph += walking ? (2 * Math.PI * Math.abs(fromX) * (1 / 2.3) * dt) / stride(0, H) : 0;
      const pose = walking ? mix(gait(s.b.ph, 0), CARRY_UP, 0.75) : mix(CARRY_UP, SQUAT, downK);
      s.b.pose = still ? LEAN_ON : mix(s.b.pose, pose, approach(dt, 12));
      s.b.pose = feel(s.b.pose, s.bb, H, -1);
      s.b.f = -1;
      const jb = solve(s.b.pose, d, s.b.x, groundCard, -1, {
        reachA: {
          target: { x: card.x + card.w + tx.x - 0.1 * H, y: card.y + card.h + tx.y },
          w: 1,
        },
        reachB: {
          target: { x: card.x + card.w + tx.x - 0.3 * H, y: card.y + card.h + tx.y },
          w: 1,
        },
      });
      drawFigure(figure(el, "b"), jb, d, { groundY: groundCard });
    } else {
      const restX = card.x + card.w + 0.3 * H;
      s.b.x += (restX - s.b.x) * approach(dt, 6);
      const pose = { ...LEAN_ON, head: LEAN_ON.head + 0.04 * Math.sin(s.t * 1.1) };
      s.b.pose = still ? pose : mix(s.b.pose, pose, approach(dt, 7));
      const bPose = feel(s.b.pose, s.bb, H, -1);
      const gaze = s.pointer
        ? gazeTo(s.pointer, { x: s.b.x, y: groundCard - 0.9 * H }, H)
        : undefined;
      const jb = solve(bPose, d, s.b.x, groundCard, -1, {
        lift: -crouch(s.bb, H),
        reachA: { target: { x: card.x + card.w + 0.04 * H, y: card.y + 0.12 * H }, w: 1, bend: -1 },
        gaze,
      });
      drawFigure(figure(el, "b"), jb, d, { groundY: groundCard });
    }

    // A carries the front end, then becomes the greeter
    const groundCta = cta.y + cta.h + d.stroke * 0.5;
    const ax = card.x + tx.x - 0.22 * H;
    const A = s.ab;
    if (carrying) {
      s.a.x = ax;
      A.x = ax;
      A.vx = 0;
      s.a.ph = s.b.ph + 0.9;
      const pose = walking ? mix(gait(s.a.ph, 0), CARRY_UP, 0.75) : mix(CARRY_UP, SQUAT, downK);
      s.a.pose = still ? FRONT : mix(s.a.pose, pose, approach(dt, 12));
      s.a.f = -1;
      s.greet = "walk";
      s.gt = 0;
      A.step(dt);
      const ja = solve(feel(s.a.pose, A, H, -1), d, s.a.x, groundCard, -1, {
        lift: -crouch(A, H),
        reachA: { target: { x: card.x + tx.x + 0.1 * H, y: card.y + card.h + tx.y }, w: 1 },
        reachB: { target: { x: card.x + tx.x + 0.3 * H, y: card.y + card.h + tx.y }, w: 1 },
      });
      drawFigure(figure(el, "a"), ja, d, { groundY: groundCard });
    } else {
      const prev = s.gt;
      s.gt += dt;
      const crossed = (at: number) => prev < at && s.gt >= at;
      const entered = prev === 0;
      const standX = cta.x + cta.w + 0.75 * H;
      const ctaMid: Vec = { x: cta.x + cta.w, y: cta.y + cta.h * 0.5 };
      const nearPointer =
        !!s.pointer && Math.hypot(s.pointer.x - A.x, s.pointer.y - (groundCta - 0.5 * H)) < 2 * H;
      const idle = s.t - s.idleSince;
      const go = (g: Greet) => {
        s.greet = g;
        s.gt = 0;
      };
      const maxRun = 5.2 * H;

      // ── behaviour ──
      if (still) {
        s.greet = "point";
        A.x = standX;
        A.y = 0;
        A.grounded = true;
        s.landed = true;
        s.a.f = 0;
      } else if (s.greet === "walk") {
        if (!s.landed && A.grounded) {
          if (A.x - standX > 2.4 * H) {
            // run out with momentum
            A.seek(standX, maxRun, 9 * H, dt);
          } else {
            // then leap up onto the button's level, timed to land beside it
            const rise = groundCard - groundCta;
            A.y = -rise;
            const vy = Math.sqrt(2 * A.gravity * (Math.max(0, rise) + 0.55 * H));
            const tUp = vy / A.gravity;
            const tDown = Math.sqrt((2 * 0.55 * H) / A.gravity);
            A.jump(vy, (standX - A.x) / (tUp + tDown));
            s.landed = true;
          }
        }
      } else if (s.greet === "wave" && s.gt > 1.6) go("point");
      else if (s.greet === "point" && s.gt > 1.1) go("shove");
      else if (s.greet === "shove" && s.gt > SHOVE_TIME) {
        go("idle");
        s.idleSince = s.t;
      } else if (s.greet === "idle") {
        if (s.hover) go("cheer");
        else if (nearPointer) go("flinch");
        else if (idle > 10) go("knock");
        else if (idle - dt < 4 && idle >= 4) go("beckon");
      } else if (s.greet === "cheer" && !s.hover && A.grounded && s.gt > 0.5) go("idle");
      else if (s.greet === "flinch" && s.gt > 1.1 && A.grounded) go("idle");
      else if (s.greet === "beckon" && s.gt > BECKON_TIME) go("idle");
      else if (s.greet === "knock" && s.gt > KNOCK_TIME) {
        go("idle");
        s.idleSince = s.t - 2; // knock again sooner if they still do not move
      }

      // ── physics ──
      if (s.greet === "flinch" && entered) {
        const away = s.pointer && s.pointer.x < A.x ? 1 : -1;
        A.jump(3.6 * H, away * 3.2 * H);
      }
      if (s.greet === "cheer" && A.grounded && s.hover && A.squash.x < 0.4) A.jump(5.4 * H, 0);
      const landing = A.step(dt);
      if (landing && !still) {
        dust(el, A.x, groundCta, 0, Math.min(1.4, landing.speed / (9 * H)));
        if (s.greet === "walk") go("wave");
      }
      const settle =
        s.greet === "idle" ||
        s.greet === "wave" ||
        s.greet === "point" ||
        s.greet === "beckon" ||
        s.greet === "knock" ||
        (s.greet === "flinch" && s.gt > 0.25);
      if (settle && A.grounded && s.landed) A.seek(standX, 2.5 * H, 10 * H, dt);

      // skidding: braking hard on the ground kicks up dust
      s.skid += dt;
      if (A.grounded && A.vx * A.ax < 0 && Math.abs(A.vx) > 1.2 * H && s.skid > 0.05) {
        s.skid = 0;
        dust(
          el,
          A.x + Math.sign(A.vx) * 0.1 * H,
          s.landed ? groundCta : groundCard,
          Math.sign(A.vx),
          0.5,
        );
      }

      // ── pose ──
      const moving = Math.abs(A.vx) > 0.15 * H;
      const run = clamp01(Math.abs(A.vx) / maxRun);
      if (A.grounded && moving) s.a.ph += (2 * Math.PI * Math.abs(A.vx) * dt) / stride(run, H);
      let pose: Pose;
      let fTarget = 0;
      let reachA: { target: Vec; w: number; bend?: number } | undefined;
      if (s.greet === "walk" || (moving && A.grounded && s.greet !== "shove")) {
        pose = mix(FRONT, gait(s.a.ph, run), smooth(Math.abs(A.vx) / (0.8 * H)));
        if (moving) fTarget = Math.sign(A.vx);
      } else if (s.greet === "wave") {
        pose = { ...FRONT, ...pick(wave(s.gt)) };
      } else if (s.greet === "point") {
        pose = { ...FRONT, head: 0.05 };
        reachA = { target: ctaMid, w: smooth(s.gt / 0.4), bend: -1 };
        fTarget = -0.35;
      } else if (s.greet === "shove") {
        // wind back, drive through; on contact the button takes the hit and the figure recoils
        const sh = shove(s.gt);
        pose = { ...FRONT, ...pick(sh.pose) };
        const contact = smooth(clamp01(s.gt / 0.3));
        reachA = {
          target: { x: ctaMid.x - sh.push * 10, y: ctaMid.y },
          w: contact * 0.95,
          bend: -1,
        };
        fTarget = -0.6;
        if (crossed(0.36)) {
          hit(ctaEl, { x: -820, r: -14 }, 0.9);
          sparks(el, ctaMid.x - 4, ctaMid.y, Math.PI, 1.3, 1.1);
          A.vx = 1.1 * H;
        }
      } else if (s.greet === "flinch") {
        pose = mix(STARTLE, FRONT, smooth((s.gt - 0.5) / 0.5));
      } else if (s.greet === "cheer") {
        pose = { ...cheer(s.gt).pose };
      } else if (s.greet === "beckon") {
        pose = { ...FRONT, ...pick(beckon(s.gt)) };
      } else if (s.greet === "knock") {
        pose = { ...FRONT, ...pick(knock(s.gt)) };
      } else {
        pose = idling(s.t);
      }
      s.a.f += (fTarget - s.a.f) * approach(dt, 9);
      s.a.pose = still ? pose : mix(s.a.pose, pose, approach(dt, moving ? 16 : 10));
      const gaze =
        s.pointer && (s.greet === "idle" || s.greet === "cheer" || s.greet === "beckon")
          ? gazeTo(s.pointer, { x: A.x, y: groundCta - 0.9 * H }, H)
          : s.greet === "knock"
            ? { x: 0, y: 0.03 * H }
            : undefined;
      // before the leap the figure stands on the card's level, after it on the button's
      const ground = s.landed ? groundCta : groundCard;
      const ja = solve(feel(s.a.pose, A, H, s.a.f), d, A.x, ground, s.a.f, {
        reachA,
        gaze,
        lift: A.y - crouch(A, H),
      });
      // each rap lands on the glass: the whole hero takes a jolt, with a spark at the knuckles
      if (s.greet === "knock") {
        for (const r of [0.47, 0.74, 1.01]) {
          if (crossed(r)) {
            hit(el.closest("section"), { y: 150, x: (r === 0.74 ? -1 : 1) * 90 }, 1.6);
            sparks(el, ja.handA.x, ja.handA.y, -Math.PI / 2, Math.PI * 2, 0.35);
          }
        }
      }
      drawFigure(figure(el, "a"), ja, d, { groundY: ground });
    }
  });

  // pointer, hover and idleness
  useEffect(() => {
    const onMove = (e: PointerEvent) => {
      const s = sim.current;
      if (!s) return;
      s.pointer = { x: e.clientX - s.stageLeft, y: e.clientY + window.scrollY - s.stageTop };
      s.idleSince = s.t;
      const cta = s.cta;
      s.hover =
        !!cta &&
        s.pointer.x >= cta.x &&
        s.pointer.x <= cta.x + cta.w &&
        s.pointer.y >= cta.y &&
        s.pointer.y <= cta.y + cta.h;
    };
    const onScroll = () => {
      const s = sim.current;
      if (s) s.idleSince = s.t;
    };
    const onLeave = () => {
      const s = sim.current;
      if (s) {
        s.pointer = null;
        s.hover = false;
      }
    };
    window.addEventListener("pointermove", onMove, { passive: true });
    window.addEventListener("scroll", onScroll, { passive: true });
    document.addEventListener("pointerleave", onLeave);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("scroll", onScroll);
      document.removeEventListener("pointerleave", onLeave);
      document
        .querySelector<HTMLElement>('[data-fig="readout"]')
        ?.style.removeProperty("transform");
      document.querySelector<HTMLElement>('[data-fig="cta"]')?.style.removeProperty("transform");
    };
  }, []);

  return (
    <svg
      ref={svg}
      aria-hidden
      className="pointer-events-none absolute inset-0 z-[25] hidden h-full w-full overflow-visible lg:block"
    >
      <FigureGlyph name="b" />
      <FigureGlyph name="a" />
      <Particles />
    </svg>
  );
}

/** The upper body of a keyed pose: arm, lean and head (the legs keep the stance). */
function pick(p: Pose): Partial<Pose> {
  return { shA: p.shA, elA: p.elA, lean: p.lean, head: p.head };
}

/** A small head shift towards a point: looking at it. */
function gazeTo(at: Vec, from: Vec, H: number): Vec {
  const dx = at.x - from.x;
  const dy = at.y - from.y;
  const len = Math.hypot(dx, dy) || 1;
  const k = Math.min(1, len / (4 * H));
  return { x: (dx / len) * 0.06 * H * k, y: (dy / len) * 0.04 * H * k };
}

export function HeroCrew() {
  return FIGURES_ON ? <HeroCrewScene /> : null;
}
