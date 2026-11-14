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
      pointer: null,
      hover: false,
    });
    s.t += dt;
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
    const carrying = downK < 1;
    const walking = inK < 1;

    // B carries the back end and then leans on the card
    const bx = card.x + card.w + tx.x + 0.22 * H;
    if (carrying) {
      s.b.x = bx;
      s.b.ph += walking ? (2 * Math.PI * Math.abs(fromX) * (1 / 2.3) * dt) / stride(0, H) : 0;
      const pose = walking ? mix(gait(s.b.ph, 0), CARRY_UP, 0.75) : mix(CARRY_UP, SQUAT, downK);
      s.b.pose = still ? LEAN_ON : mix(s.b.pose, pose, approach(dt, 12));
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
      const gaze = s.pointer
        ? gazeTo(s.pointer, { x: s.b.x, y: groundCard - 0.9 * H }, H)
        : undefined;
      const jb = solve(s.b.pose, d, s.b.x, groundCard, -1, {
        reachA: { target: { x: card.x + card.w + 0.04 * H, y: card.y + 0.12 * H }, w: 1, bend: -1 },
        gaze,
      });
      drawFigure(figure(el, "b"), jb, d, { groundY: groundCard });
    }

    // A carries the front end, then becomes the greeter
    const groundCta = cta.y + cta.h + d.stroke * 0.5;
    const ax = card.x + tx.x - 0.22 * H;
    if (carrying) {
      s.a.x = ax;
      s.a.ph = s.b.ph + 0.9;
      const pose = walking ? mix(gait(s.a.ph, 0), CARRY_UP, 0.75) : mix(CARRY_UP, SQUAT, downK);
      s.a.pose = still ? FRONT : mix(s.a.pose, pose, approach(dt, 12));
      s.a.f = -1;
      s.greet = "walk";
      s.gt = 0;
      const ja = solve(s.a.pose, d, s.a.x, groundCard, -1, {
        reachA: { target: { x: card.x + tx.x + 0.1 * H, y: card.y + card.h + tx.y }, w: 1 },
        reachB: { target: { x: card.x + tx.x + 0.3 * H, y: card.y + card.h + tx.y }, w: 1 },
      });
      drawFigure(figure(el, "a"), ja, d, { groundY: groundCard });
    } else {
      s.gt += dt;
      const standX = cta.x + cta.w + 0.75 * H;
      const ctaMid: Vec = { x: cta.x + cta.w, y: cta.y + cta.h * 0.5 };
      const nearPointer =
        !!s.pointer && Math.hypot(s.pointer.x - s.a.x, s.pointer.y - (groundCta - 0.5 * H)) < 2 * H;
      const idle = s.t - s.idleSince;

      // state machine for the greeter
      if (still) {
        s.greet = "point";
        s.a.x = standX;
        s.a.f = 0;
      } else if (s.greet === "walk") {
        const gap = standX - s.a.x;
        if (Math.abs(gap) < 1) {
          s.greet = "wave";
          s.gt = 0;
        } else {
          const step = Math.sign(gap) * Math.min(Math.abs(gap), 4.6 * H * dt);
          s.a.x += step;
          s.a.ph += (2 * Math.PI * Math.abs(step)) / stride(0.75, H);
        }
      } else if (s.greet === "wave" && s.gt > 1.5) {
        s.greet = "point";
        s.gt = 0;
      } else if (s.greet === "point" && s.gt > 1.1) {
        s.greet = "shove";
        s.gt = 0;
      } else if (s.greet === "shove" && s.gt > SHOVE_TIME) {
        s.greet = "idle";
        s.gt = 0;
        s.idleSince = s.t;
      } else if (s.greet === "idle") {
        if (s.hover) {
          s.greet = "cheer";
          s.gt = 0;
        } else if (nearPointer) {
          s.greet = "flinch";
          s.gt = 0;
        } else if (idle > 14) {
          s.greet = "knock";
          s.gt = 0;
        } else if (idle > 7 && idle < 7.05) {
          s.greet = "beckon";
          s.gt = 0;
        }
      } else if (s.greet === "cheer" && (!s.hover || s.gt > 2.5)) {
        s.greet = "idle";
        s.gt = 0;
      } else if (s.greet === "flinch" && s.gt > 0.9) {
        s.greet = "idle";
        s.gt = 0;
      } else if (s.greet === "beckon" && s.gt > BECKON_TIME) {
        s.greet = "idle";
        s.gt = 0;
      } else if (s.greet === "knock" && s.gt > KNOCK_TIME) {
        s.greet = "idle";
        s.gt = 0;
        s.idleSince = s.t - 2; // knock again sooner if they still do not move
      }

      let pose: Pose;
      let fTarget = 0;
      let reachA: { target: Vec; w: number; bend?: number } | undefined;
      let xTarget = standX;
      let push = 0;
      let hop = 0;
      if (s.greet === "walk") {
        pose = gait(s.a.ph, 0.75);
        fTarget = -1;
      } else if (s.greet === "wave") {
        pose = { ...FRONT, ...pick(wave(s.gt)) };
      } else if (s.greet === "point") {
        pose = { ...FRONT, head: 0.05 };
        reachA = { target: ctaMid, w: smooth(s.gt / 0.4), bend: -1 };
        fTarget = -0.35;
      } else if (s.greet === "shove") {
        // wind back, drive through, hold, recover; the button travels with the hand
        const sh = shove(s.gt);
        pose = { ...FRONT, ...pick(sh.pose) };
        push = sh.push;
        const contact = smooth(clamp01(s.gt / 0.3));
        reachA = { target: { x: ctaMid.x - push * 12, y: ctaMid.y }, w: contact * 0.95, bend: -1 };
        fTarget = -0.6;
        xTarget = standX - 0.1 * H - push * 0.12 * H;
      } else if (s.greet === "flinch") {
        const k = s.gt / 0.9;
        pose = mix(STARTLE, FRONT, smooth((k - 0.55) / 0.45));
        const away = s.pointer && s.pointer.x < s.a.x ? 1 : -1;
        xTarget = standX + away * 0.45 * H * Math.sin(Math.PI * Math.min(1, k * 1.3));
      } else if (s.greet === "cheer") {
        const ch = cheer(s.gt);
        pose = ch.pose;
        hop = ch.lift * H;
      } else if (s.greet === "beckon") {
        pose = { ...FRONT, ...pick(beckon(s.gt)) };
      } else {
        pose = { ...FRONT, ...pick(knock(s.gt)) };
      }
      if (s.greet !== "walk") s.a.x += (xTarget - s.a.x) * approach(dt, 10);
      s.a.f += (fTarget - s.a.f) * approach(dt, 8);
      s.a.pose = still ? pose : mix(s.a.pose, pose, approach(dt, s.greet === "walk" ? 16 : 9));

      // the real button moves when shoved
      ctaEl.style.transform = push > 0.02 ? `translate3d(${(-push * 12).toFixed(1)}px, 0, 0)` : "";
      const gaze =
        s.pointer && (s.greet === "idle" || s.greet === "cheer" || s.greet === "beckon")
          ? gazeTo(s.pointer, { x: s.a.x, y: groundCta - 0.9 * H }, H)
          : s.greet === "knock"
            ? { x: 0, y: 0.03 * H }
            : undefined;
      const ja = solve(s.a.pose, d, s.a.x, groundCta, s.a.f, { reachA, gaze, lift: hop });
      drawFigure(figure(el, "a"), ja, d, { groundY: groundCta });
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
