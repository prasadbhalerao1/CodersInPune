"use client";

import { useEffect, useRef, useSyncExternalStore } from "react";

import { drawBody, drawShadow, readInk, type Ink } from "./canvas";
import { GETUP_TIME, getup } from "./fight";
import { wave } from "./gestures";
import { Spring, knock } from "./physics";
import { Ragdoll, type Bounds, type Plat } from "./ragdoll";
import {
  STAND,
  THINK,
  approach,
  clamp01,
  dims,
  gait,
  mix,
  smooth,
  solve,
  stride,
  type Dims,
  type Joints,
  type Pose,
  type Reach,
  type Vec,
} from "./rig";
import { finished, register } from "./director";
import { FIGURES_ON } from "./stage";
import { EASE } from "./track";

/**
 * The interlude: a short film that plays when the reader has been still for a while.
 *
 * A figure strolls in along the bottom of the screen, stops under a heading and thinks. He takes
 * a rope from his pocket, whirls it like a lasso and throws it; it catches in a letter of the
 * heading. He takes a run and swings on it, and mid-swing the letter comes out of the heading.
 * He slams into the ground, gets up rubbing his head, coils the rope back into his pocket, picks
 * the letter up, aims, and throws it back. It lands in its slot, but crooked. So he climbs the
 * page, hopping from line to line, straightens the letter by hand, jumps back down and gives the
 * reader a thumbs up. Then he takes out a pencil, draws a door, opens it towards the reader,
 * walks in and shuts it; a moment later it opens again, he leans out, waves goodbye, and shuts it.
 *
 * The letter is the real glyph on the page: that one character is wrapped in a span for the
 * film and unwrapped afterwards. Everything is physical: ballistic jumps that land where they
 * aim, a pendulum on a rope that shortens as he pulls himself up, a Verlet ragdoll for the fall,
 * a rigid letter that bounces and settles, springs for the wobbles. Scrolling away ends the film
 * at once and puts the page back exactly as it was.
 */

const G = 2600;
const PREFERRED = "oaepdbgqOAPDBQ";

type Ledge = { left: number; right: number; y: number };
type Stage =
  | "enter"
  | "think"
  | "pocket"
  | "whirl"
  | "throw"
  | "tug"
  | "runup"
  | "swing"
  | "fall"
  | "getup"
  | "rub"
  | "reel"
  | "fetch"
  | "pick"
  | "aim"
  | "toss"
  | "watch"
  | "climb"
  | "adjust"
  | "down"
  | "thumbs"
  | "pencil"
  | "draw"
  | "open"
  | "enterDoor"
  | "shut"
  | "peek"
  | "bye"
  | "slam"
  | "linger"
  | "fade";

type Letter = {
  span: HTMLSpanElement;
  restore: () => void;
  sx: number;
  sy: number;
  w: number;
  h: number;
  x: number;
  y: number;
  vx: number;
  vy: number;
  a: number;
  av: number;
  mode: "slot" | "free" | "held" | "flying" | "seated";
  wobble: Spring;
  tilt: number;
  fly: {
    x0: number;
    y0: number;
    vx: number;
    vy: number;
    a0: number;
    a1: number;
    T: number;
    t: number;
  } | null;
};

type Arc = {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  vx: number;
  vy: number;
  T: number;
  t: number;
};

type Spark = {
  x: number;
  y: number;
  vx: number;
  vy: number;
  age: number;
  life: number;
  kind: "spark" | "dust";
};

const lerp = (a: number, b: number, k: number) => a + (b - a) * k;

// ── finding the stage ────────────────────────────────────────────────────────────────────

function textLedges(sy: number, floor: number): Ledge[] {
  const lines: Ledge[] = [];
  const els = document.querySelectorAll<HTMLElement>(
    "main h1, main h2, main h3, main p, main li, main blockquote",
  );
  const r = document.createRange();
  for (const el of els) {
    const box = el.getBoundingClientRect();
    if (box.bottom < 80 || box.top > window.innerHeight || box.width < 40) continue;
    if (el.closest("[aria-hidden='true']")) continue;
    r.selectNodeContents(el);
    for (const rc of r.getClientRects()) {
      if (rc.width < 24 || rc.height < 10) continue;
      const y = rc.top + rc.height * 0.2 + sy;
      if (y < sy + 96 || y > floor - 10) continue;
      lines.push({ left: rc.left, right: rc.right, y });
    }
  }
  for (const el of document.querySelectorAll<HTMLElement>(".glass, .glass-dark, .glass-clear")) {
    if (el.closest("header")) continue;
    const b = el.getBoundingClientRect();
    const y = b.top + sy;
    if (b.width < 90 || y < sy + 96 || y > floor - 10) continue;
    lines.push({ left: b.left + 4, right: b.right - 4, y });
  }
  // merge runs on the same line
  lines.sort((a, b) => a.y - b.y || a.left - b.left);
  const out: Ledge[] = [];
  for (const l of lines) {
    const prev = out[out.length - 1];
    if (prev && Math.abs(prev.y - l.y) < 5 && l.left <= prev.right + 14)
      prev.right = Math.max(prev.right, l.right);
    else out.push({ ...l });
  }
  return out;
}

function pickLetter(H: number, floor: number): { node: Text; index: number; rect: DOMRect } | null {
  const sy = window.scrollY;
  const range = document.createRange();
  const headings = [...document.querySelectorAll<HTMLElement>("main h2, main h1")];
  const options: { node: Text; index: number; rect: DOMRect; score: number }[] = [];
  for (const h of headings) {
    const fs = parseFloat(getComputedStyle(h).fontSize);
    if (fs < 40) continue;
    const box = h.getBoundingClientRect();
    if (box.top < 100 || box.bottom > window.innerHeight - 40) continue;
    const walker = document.createTreeWalker(h, NodeFilter.SHOW_TEXT);
    let n: Node | null;
    while ((n = walker.nextNode())) {
      const t = n as Text;
      const s = t.data;
      for (let i = 1; i < s.length - 1; i++) {
        const ch = s[i]!;
        if (!PREFERRED.includes(ch)) continue;
        range.setStart(t, i);
        range.setEnd(t, i + 1);
        const rect = range.getBoundingClientRect();
        if (rect.width < 12 || rect.top < 110) continue;
        // room below for the swing and the fall
        if (floor - (rect.bottom + sy) < 3.8 * H) continue;
        const centred =
          1 - Math.abs(rect.left + rect.width / 2 - window.innerWidth / 2) / window.innerWidth;
        options.push({ node: t, index: i, rect, score: centred + rect.height / 200 });
      }
    }
  }
  options.sort((a, b) => b.score - a.score);
  const best = options[0];
  return best ? { node: best.node, index: best.index, rect: best.rect } : null;
}

function wrap(node: Text, index: number): { span: HTMLSpanElement; restore: () => void } {
  const parent = node.parentNode!;
  const letter = node.splitText(index);
  letter.splitText(1);
  const span = document.createElement("span");
  span.setAttribute("data-interlude-letter", "");
  span.style.display = "inline-block";
  span.style.transformOrigin = "50% 55%";
  span.style.willChange = "transform";
  parent.insertBefore(span, letter);
  span.appendChild(letter);
  return {
    span,
    restore: () => {
      if (!span.isConnected) return;
      span.replaceWith(letter);
      parent.normalize();
    },
  };
}

/** A path of hops from `from` to `goal` over the ledges, each one a jump a person could make. */
function route(ledges: Ledge[], from: Ledge, goal: Ledge, H: number): Ledge[] | null {
  const all = [from, ...ledges.filter((l) => l !== from)];
  const goalI = all.indexOf(goal);
  if (goalI < 0) return null;
  const prev = new Map<number, number>();
  const seen = new Set([0]);
  const q = [0];
  while (q.length) {
    const i = q.shift()!;
    if (i === goalI) break;
    const a = all[i]!;
    all.forEach((b, k) => {
      if (seen.has(k)) return;
      const up = a.y - b.y;
      if (up > 2.3 * H || up < -6 * H) return;
      const gap = Math.max(0, b.left - a.right, a.left - b.right);
      if (gap > 2.4 * H) return;
      if (b.right - b.left < 0.5 * H) return;
      seen.add(k);
      prev.set(k, i);
      q.push(k);
    });
  }
  if (!seen.has(goalI)) return null;
  const path: Ledge[] = [];
  for (let k: number | undefined = goalI; k !== undefined && k !== 0; k = prev.get(k))
    path.unshift(all[k]!);
  return path;
}

/** A ballistic jump from (x0, y0) to (x1, y1), rising `over` above the higher end. */
function arc(x0: number, y0: number, x1: number, y1: number, over: number): Arc {
  const top = Math.min(y0, y1) - over;
  const vy = -Math.sqrt(2 * G * (y0 - top));
  const T = -vy / G + Math.sqrt((2 * (y1 - top)) / G);
  return { x0, y0, x1, y1, vx: (x1 - x0) / T, vy, T, t: 0 };
}
const arcAt = (a: Arc, t: number): Vec => ({
  x: a.x0 + a.vx * t,
  y: a.y0 + a.vy * t + 0.5 * G * t * t,
});

// ── the film ─────────────────────────────────────────────────────────────────────────────

type Film = {
  st: Stage;
  t: number;
  clock: number;
  H: number;
  d: Dims;
  ink: Ink;
  sy0: number;
  floor: number;
  side: number; // which side of the letter he works from (-1 left, 1 right)
  x: number;
  y: number;
  vx: number;
  f: number;
  ph: number;
  pose: Pose;
  squash: Spring;
  j: Joints | null;
  arc: Arc | null;
  rag: Ragdoll | null;
  quiet: number;
  from: Joints | null;
  letter: Letter;
  anchor: Vec;
  rope: "none" | "coil" | "whirl" | "flying" | "hooked" | "slack" | "reel";
  ropeEnd: Vec;
  ropeLen: number;
  loopFly: Arc | null;
  hand: Vec; // pendulum: where his hands are on the rope
  handV: Vec;
  ledges: Ledge[];
  path: Ledge[];
  hop: number;
  ledge: Ledge;
  door: {
    x0: number;
    y0: number;
    w: number;
    h: number;
    drawn: number;
    theta: number;
    alpha: number;
  } | null;
  alpha: number;
  pencil: boolean;
  thumb: boolean;
  fx: Spark[];
  seed: number;
};

function rnd(f: Film) {
  let x = f.seed;
  x ^= x << 13;
  x ^= x >>> 17;
  x ^= x << 5;
  f.seed = x >>> 0;
  return (f.seed % 10000) / 10000;
}

function InterludeLayer() {
  const canvas = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const cv = canvas.current;
    const ctx = cv?.getContext("2d");
    if (!cv || !ctx) return;
    let dpr = 1;
    const fit = () => {
      dpr = Math.min(2, window.devicePixelRatio || 1);
      cv.width = Math.round(window.innerWidth * dpr);
      cv.height = Math.round(window.innerHeight * dpr);
    };
    fit();

    let film: Film | null = null;
    let raf = 0;
    let last = 0;
    const onResize = () => fit();
    window.addEventListener("resize", onResize);

    const end = () => {
      if (!film) return;
      film.letter.span.style.transform = "";
      film.letter.restore();
      film = null;
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(0, 0, cv.width, cv.height);
      cancelAnimationFrame(raf);
      raf = 0;
      finished("lasso");
    };

    const start = () => {
      const H = window.innerWidth < 640 ? 70 : 96;
      const sy = window.scrollY;
      const floor = sy + window.innerHeight - 10;
      const pick = pickLetter(H, floor);
      if (!pick) return false;
      const { span, restore } = wrap(pick.node, pick.index);
      const r = span.getBoundingClientRect();
      const letter: Letter = {
        span,
        restore,
        sx: r.left + r.width / 2,
        sy: r.top + r.height / 2 + sy,
        w: r.width,
        h: r.height,
        x: 0,
        y: 0,
        vx: 0,
        vy: 0,
        a: 0,
        av: 0,
        mode: "slot",
        wobble: new Spring(260, 9),
        tilt: 0,
        fly: null,
      };
      letter.x = letter.sx;
      letter.y = letter.sy;
      const side = letter.sx > window.innerWidth / 2 ? -1 : 1;
      const ground: Ledge = { left: 0, right: window.innerWidth, y: floor };
      const d = dims(H);
      film = {
        st: "enter",
        t: 0,
        clock: 0,
        H,
        d,
        ink: readInk(),
        sy0: sy,
        floor,
        side,
        // he enters from the edge of the screen on his side, strolling
        x: side < 0 ? -0.6 * H : window.innerWidth + 0.6 * H,
        y: floor,
        vx: 0,
        f: -side,
        ph: 0,
        pose: STAND,
        squash: new Spring(300, 15),
        j: null,
        arc: null,
        rag: null,
        quiet: 0,
        from: null,
        letter,
        anchor: { x: letter.sx, y: letter.sy },
        rope: "none",
        ropeEnd: { x: 0, y: 0 },
        ropeLen: 0,
        loopFly: null,
        hand: { x: 0, y: 0 },
        handV: { x: 0, y: 0 },
        ledges: [],
        path: [],
        hop: 0,
        ledge: ground,
        door: null,
        alpha: 1,
        pencil: false,
        thumb: false,
        fx: [],
        seed: 9001,
      };
      last = 0;
      raf = requestAnimationFrame(frame);
      return true;
    };

    const unregister = register({
      name: "lasso",
      idleAfter: 9,
      ready: () => {
        const H = window.innerWidth < 640 ? 70 : 96;
        return !!pickLetter(H, window.scrollY + window.innerHeight - 10);
      },
      start: () => {
        start();
      },
      abort: () => end(),
    });

    const frame = (now: number) => {
      const dt = last ? Math.min(0.033, (now - last) / 1000) : 0;
      last = now;
      if (!film) return;
      raf = requestAnimationFrame(frame);
      if (dt === 0) return;
      stepAll(film, dt);
      if (film) draw(film);
    };

    // ── helpers ──
    const go = (f: Film, st: Stage) => {
      f.st = st;
      f.t = 0;
    };
    const burst = (f: Film, x: number, y: number, kind: "spark" | "dust", power: number) => {
      const n = Math.round((kind === "spark" ? 10 : 6) * (0.6 + power));
      for (let i = 0; i < n; i++) {
        const a =
          kind === "spark" ? rnd(f) * Math.PI * 2 : (i % 2 ? 0 : Math.PI) + (rnd(f) - 0.5) * 0.6;
        const v = (kind === "spark" ? 300 + 500 * rnd(f) : 50 + 140 * rnd(f)) * (0.6 + 0.5 * power);
        f.fx.push({
          x,
          y,
          vx: Math.cos(a) * v,
          vy: Math.sin(a) * v - (kind === "dust" ? 40 : 0),
          age: 0,
          life: kind === "spark" ? 0.3 : 0.6,
          kind,
        });
      }
    };
    /** Walk (or run) towards x with momentum; returns true once there and stopped. */
    const walkTo = (f: Film, tx: number, speed: number, dt: number) => {
      const gap = tx - f.x;
      const stop = (f.vx * f.vx) / (2 * 9 * f.H);
      const want = Math.abs(gap) < 2 ? 0 : Math.abs(gap) <= stop ? 0 : Math.sign(gap) * speed;
      const dv = want - f.vx;
      f.vx +=
        Math.sign(dv) *
        Math.min(Math.abs(dv), (Math.abs(want) > Math.abs(f.vx) ? 7 : 11) * f.H * dt);
      if (
        Math.abs(gap) < Math.abs(f.vx * dt) ||
        (Math.abs(gap) < 2 && Math.abs(f.vx) < 0.2 * f.H)
      ) {
        f.x = tx;
        f.vx = 0;
        return true;
      }
      f.x += f.vx * dt;
      if (Math.abs(f.vx) > 0.1 * f.H) f.f = Math.sign(f.vx);
      const run = clamp01((Math.abs(f.vx) - 1.3 * f.H) / (3.4 * f.H));
      f.ph += (2 * Math.PI * Math.abs(f.vx) * dt) / stride(run, f.H);
      f.pose = mix(f.pose, gait(f.ph, run), approach(dt, 20));
      return false;
    };
    const settle = (f: Film, p: Pose, dt: number, rate = 9) => {
      f.pose = mix(f.pose, p, approach(dt, rate));
    };
    const turnTo = (f: Film, target: number, dt: number) => {
      f.f += (target - f.f) * approach(dt, 10);
    };
    const handTo = (target: Vec, w = 1, bend = -1): Reach => ({ target, w, bend });

    // ── the script ──
    const step = (f: Film, dt: number) => {
      f.t += dt;
      f.clock += dt;
      f.squash.step(dt);
      const { H, d, letter: L } = f;
      const anchor = { x: L.sx, y: L.sy };
      let reachA: Reach | undefined;
      let reachB: Reach | undefined;
      let lift = 0;
      let gaze: Vec | undefined;
      let pelvisY: number | undefined;
      f.thumb = false;

      // letter physics (whatever stage)
      stepLetter(f, dt);

      switch (f.st) {
        case "enter": {
          // stroll in and stop beneath the heading, a couple of body lengths off
          const spot = Math.max(
            0.6 * H,
            Math.min(window.innerWidth - 0.6 * H, anchor.x - f.side * 3.3 * H),
          );
          if (walkTo(f, spot, 1.25 * H, dt)) go(f, "think");
          break;
        }
        case "think": {
          turnTo(f, f.side, dt);
          // look up at the heading, hand on chin; halfway, a glance at the reader
          const glance = f.t > 1.1 && f.t < 1.6;
          if (glance) turnTo(f, 0, dt * 2);
          settle(f, { ...THINK, head: glance ? 0.1 : -0.35 + 0.05 * Math.sin(f.t * 2) }, dt);
          gaze = { x: f.side * 0.03 * H, y: glance ? 0 : -0.05 * H };
          if (f.t > 2.2) go(f, "pocket");
          break;
        }
        case "pocket": {
          turnTo(f, f.side, dt);
          // into the pocket, out with a coil of rope
          const k = f.t / 0.7;
          const pocket = { x: f.x + f.f * 0.1 * H, y: f.y - 0.42 * H };
          const out = { x: f.x + f.f * 0.28 * H, y: f.y - 0.72 * H };
          settle(
            f,
            { ...STAND, lean: 0.05 + 0.1 * Math.sin(Math.PI * clamp01(k)), head: 0.25 },
            dt,
          );
          reachA = handTo(
            k < 0.5
              ? pocket
              : {
                  x: lerp(pocket.x, out.x, smooth((k - 0.5) * 2)),
                  y: lerp(pocket.y, out.y, smooth((k - 0.5) * 2)),
                },
            smooth(k * 3),
          );
          if (k > 0.5) f.rope = "coil";
          if (k >= 1) go(f, "whirl");
          break;
        }
        case "whirl": {
          // the loop goes round overhead, faster and wider
          const w = 7 + 5 * clamp01(f.t / 1.2);
          const centre = { x: f.x + f.f * 0.05 * H, y: f.y - 1.28 * H };
          const r = 0.1 * H;
          const ang = f.t * w;
          reachA = handTo({
            x: centre.x + Math.cos(ang) * r,
            y: centre.y + Math.sin(ang) * r * 0.4,
          });
          settle(
            f,
            {
              ...STAND,
              lean: -0.06,
              head: -0.25,
              hipA: 0.25,
              kneeA: 0.15,
              hipB: -0.25,
              kneeB: 0.1,
            },
            dt,
          );
          f.rope = "whirl";
          f.ropeEnd = {
            x: centre.x + Math.cos(ang) * 0.42 * H,
            y: centre.y - 0.08 * H + Math.sin(ang) * 0.12 * H,
          };
          if (f.t > 1.7) {
            go(f, "throw");
            // the loop flies to the letter, landing exactly on it
            const hand = f.j ? f.j.handA : centre;
            f.loopFly = arc(hand.x, hand.y, anchor.x, anchor.y - L.h * 0.15, 0.5 * H);
          }
          break;
        }
        case "throw": {
          settle(
            f,
            { ...STAND, lean: 0.18, head: -0.3, hipA: 0.4, kneeA: 0.3, hipB: -0.35, kneeB: 0.1 },
            dt,
            16,
          );
          reachA = handTo({ x: f.x + f.f * 0.5 * H, y: f.y - 1.05 * H }, 1);
          f.rope = "flying";
          if (f.loopFly) {
            f.loopFly.t += dt;
            f.ropeEnd = arcAt(f.loopFly, Math.min(f.loopFly.t, f.loopFly.T));
            if (f.loopFly.t >= f.loopFly.T) {
              f.rope = "hooked";
              L.wobble.kick(9);
              burst(f, anchor.x, anchor.y, "spark", 0.4);
              go(f, "tug");
            }
          }
          break;
        }
        case "tug": {
          // two tugs to test it: the letter wobbles but holds
          const pull = Math.max(0, Math.sin(f.t * 9)) * (f.t < 1.0 ? 1 : 0);
          settle(
            f,
            {
              ...STAND,
              lean: -0.2 - 0.18 * pull,
              head: -0.2,
              hipA: 0.45,
              kneeA: 0.35,
              hipB: -0.35,
              kneeB: 0.2,
            },
            dt,
            18,
          );
          const towards = { x: f.x + f.f * 0.42 * H, y: f.y - 0.95 * H };
          reachA = handTo(towards);
          reachB = handTo({ x: towards.x - f.f * 0.1 * H, y: towards.y + 0.08 * H });
          if (pull > 0.95 && Math.sin((f.t - dt) * 9) < 0.95) L.wobble.kick(-6);
          if (f.t > 1.25) go(f, "runup");
          break;
        }
        case "runup": {
          // gather, then a sprint at the rope and a leap onto it: the run is where the swing's
          // energy comes from
          const take = anchor.x - f.side * 1.7 * H;
          if (f.t < 0.3) {
            settle(
              f,
              { ...STAND, lean: 0.3, head: -0.2, hipA: 0.7, kneeA: 1.1, hipB: -0.2, kneeB: 0.6 },
              dt,
              12,
            );
            break;
          }
          const want = f.side * 5.2 * H;
          f.vx += Math.sign(want - f.vx) * Math.min(Math.abs(want - f.vx), 16 * H * dt);
          f.x += f.vx * dt;
          f.f = f.side;
          const run = clamp01((Math.abs(f.vx) - 1.3 * H) / (3.4 * H));
          f.ph += (2 * Math.PI * Math.abs(f.vx) * dt) / stride(run, H);
          f.pose = mix(f.pose, gait(f.ph, run), approach(dt, 22));
          if ((take - f.x) * f.side <= 0) {
            // grab the rope overhead as he leaves the ground
            const hand = { x: f.x + f.f * 0.3 * H, y: f.y - 1.2 * H };
            f.hand = hand;
            f.handV = { x: f.vx * 1.05, y: -2.4 * H };
            f.ropeLen = Math.hypot(hand.x - anchor.x, hand.y - anchor.y);
            burst(f, f.x, f.y, "dust", 0.9);
            go(f, "swing");
          }
          break;
        }
        case "swing": {
          // a pendulum on the rope; he hauls himself up a little as he goes
          const target = f.ropeLen - 0.4 * H * smooth(f.t / 0.5);
          f.handV.y += G * dt;
          f.hand.x += f.handV.x * dt;
          f.hand.y += f.handV.y * dt;
          const dx = f.hand.x - anchor.x;
          const dy = f.hand.y - anchor.y;
          const dist = Math.hypot(dx, dy) || 1;
          if (dist > target) {
            const nx = dx / dist;
            const ny = dy / dist;
            f.hand.x = anchor.x + nx * target;
            f.hand.y = anchor.y + ny * target;
            const radial = f.handV.x * nx + f.handV.y * ny;
            if (radial > 0) {
              f.handV.x -= radial * nx;
              f.handV.y -= radial * ny;
            }
          }
          const ang = Math.atan2(f.hand.x - anchor.x, f.hand.y - anchor.y); // 0 straight down
          // the body hangs from the hands along the rope, legs tucked, trailing the swing
          const dir = { x: (f.hand.x - anchor.x) / dist, y: (f.hand.y - anchor.y) / dist };
          const lag = Math.max(-0.35, Math.min(0.35, -f.handV.x / (12 * H)));
          const bodyDir = {
            x: Math.sin(Math.atan2(dir.x, dir.y) + lag),
            y: Math.cos(Math.atan2(dir.x, dir.y) + lag),
          };
          const chest = {
            x: f.hand.x + bodyDir.x * (d.upper + d.fore) * 0.9,
            y: f.hand.y + bodyDir.y * (d.upper + d.fore) * 0.9,
          };
          const pelvis = { x: chest.x + bodyDir.x * d.torso, y: chest.y + bodyDir.y * d.torso };
          f.f = f.side;
          const lean = Math.atan2(-bodyDir.x * f.f, bodyDir.y);
          const tilt = Math.atan2(bodyDir.x * f.f, bodyDir.y);
          f.pose = {
            ...STAND,
            lean,
            head: -lean * 0.4 - 0.2,
            hipA: tilt + 0.95,
            kneeA: 1.5,
            hipB: tilt + 0.6,
            kneeB: 1.25,
          };
          f.x = pelvis.x;
          pelvisY = pelvis.y;
          reachA = handTo(f.hand);
          reachB = handTo({ x: f.hand.x, y: f.hand.y + 0.05 * H });
          // mid-swing, past the bottom and rising: the letter gives
          if (f.t > 0.3 && ang * f.side > 0.06) {
            L.mode = "free";
            L.x = anchor.x;
            L.y = anchor.y;
            L.vx = f.handV.x * 0.55;
            L.vy = f.handV.y * 0.4 - 300;
            L.av = f.side * 9;
            burst(f, anchor.x, anchor.y, "spark", 1);
            f.rope = "slack";
            go(f, "fall");
            // he lets go of nothing: rope in hand, now just falling with the letter in tow
            const j0 = f.j!;
            f.rag = new Ragdoll(d);
            f.rag.fromJoints(j0, f.handV.x * 0.9, f.handV.y * 0.6, f.side * 3.5);
          }
          break;
        }
        case "fall": {
          const rag = f.rag!;
          const b: Bounds = {
            left: 4,
            right: window.innerWidth - 4,
            ceil: window.scrollY + 70,
            floor: f.floor,
          };
          const plats: Plat[] = [];
          rag.step(dt, plats, b, (hit) => {
            const power = Math.min(1.6, hit.speed / 1300);
            burst(f, hit.x, hit.y, "dust", power);
            if (hit.speed > 900) {
              burst(f, hit.x, hit.y, "spark", power * 0.6);
              knock(L.span.closest("section"), { y: Math.min(400, hit.speed * 0.16) }, 1.2);
            }
          });
          f.j = rag.joints();
          // the rope still ties his hand to the letter
          const hand = f.j.handA;
          const dx = L.x - hand.x;
          const dy = L.y - hand.y;
          const dist = Math.hypot(dx, dy) || 1;
          if (dist > f.ropeLen && L.mode === "free") {
            L.x = hand.x + (dx / dist) * f.ropeLen;
            L.y = hand.y + (dy / dist) * f.ropeLen;
            const along = (L.vx * dx + L.vy * dy) / dist;
            if (along > 0) {
              L.vx -= (along * dx) / dist;
              L.vy -= (along * dy) / dist;
            }
          }
          f.quiet = rag.speed() < 70 ? f.quiet + dt : 0;
          if (f.quiet > 0.7 && f.t > 1) {
            f.from = f.j;
            f.x = f.j.pelvis.x;
            f.y = f.floor;
            f.f = Math.sign(L.x - f.x) || 1;
            go(f, "getup");
          }
          return; // the ragdoll is the pose
        }
        case "getup": {
          const target = solve(getup(f.t), d, f.x, f.y, f.f);
          f.j = f.from ? blend(f.from, target, smooth(f.t / 0.45)) : target;
          f.pose = getup(f.t);
          if (f.t >= GETUP_TIME) go(f, "rub");
          return;
        }
        case "rub": {
          // a dazed moment: hand rubbing the head, a little sway
          settle(
            f,
            {
              ...STAND,
              lean: 0.06 + 0.04 * Math.sin(f.t * 3),
              head: 0.25 + 0.08 * Math.sin(f.t * 5),
              hipA: 0.12,
              kneeA: 0.2,
              hipB: -0.15,
              kneeB: 0.15,
            },
            dt,
          );
          const j = f.j;
          if (j)
            reachA = handTo({
              x: j.head.x + Math.cos(f.t * 16) * 0.04 * H,
              y: j.head.y - 0.07 * H + Math.sin(f.t * 16) * 0.02 * H,
            });
          if (f.t > 1.6) {
            go(f, "reel");
            f.rope = "reel";
          }
          break;
        }
        case "reel": {
          // the loop slips off the letter and the rope is hauled in, hand over hand, into the pocket
          settle(f, { ...STAND, lean: 0.1, head: 0.2 }, dt);
          const hand = f.j ? f.j.handA : { x: f.x, y: f.y - H };
          const k = smooth(f.t / 0.9);
          f.ropeEnd = { x: lerp(L.x, hand.x, k), y: lerp(L.y, hand.y, k) };
          reachA = handTo({
            x: f.x + f.f * (0.3 + 0.08 * Math.sin(f.t * 14)) * H,
            y: f.y - (0.75 + 0.06 * Math.cos(f.t * 14)) * H,
          });
          if (f.t > 0.9) reachA = handTo({ x: f.x + f.f * 0.1 * H, y: f.y - 0.42 * H });
          if (f.t > 0.9) f.rope = "none";
          if (f.t > 1.3) go(f, "fetch");
          break;
        }
        case "fetch": {
          if (walkTo(f, L.x - Math.sign(L.x - f.x || 1) * 0.42 * H, 1.3 * H, dt)) go(f, "pick");
          break;
        }
        case "pick": {
          // squat, grip, stand up holding it upright
          turnTo(f, Math.sign(L.x - f.x) || f.f, dt);
          const k = f.t / 1.0;
          const down = k < 0.45 ? smooth(k / 0.45) : 1 - smooth((k - 0.55) / 0.45);
          settle(
            f,
            mix(
              STAND,
              { ...STAND, lean: 0.55, head: 0.35, hipA: 1.25, kneeA: 2.0, hipB: 0.9, kneeB: 1.8 },
              down,
            ),
            dt,
            14,
          );
          if (k > 0.45 && L.mode !== "held") L.mode = "held";
          reachA = handTo(
            L.mode === "held" && f.j
              ? { x: f.x + f.f * 0.35 * H, y: f.y - (0.25 + 0.6 * (1 - down)) * H }
              : { x: L.x, y: L.y - L.h * 0.2 },
          );
          if (k >= 1) go(f, "aim");
          break;
        }
        case "aim": {
          // face the slot, size it up, a couple of small practice motions
          turnTo(f, Math.sign(L.sx - f.x) || f.f, dt);
          const practice = Math.sin(f.t * 6) * (f.t > 0.4 && f.t < 1.2 ? 1 : 0);
          settle(
            f,
            {
              ...STAND,
              lean: -0.08 - 0.06 * practice,
              head: -0.4,
              hipA: 0.35,
              kneeA: 0.25,
              hipB: -0.35,
              kneeB: 0.15,
            },
            dt,
            12,
          );
          reachA = handTo({
            x: f.x - f.f * (0.25 + 0.06 * practice) * H,
            y: f.y - (1.15 + 0.05 * practice) * H,
          });
          gaze = { x: f.f * 0.03 * H, y: -0.05 * H };
          if (f.t > 1.5) {
            const hand = f.j ? f.j.handA : { x: f.x, y: f.y - H };
            const T = 0.8;
            L.mode = "flying";
            // a little short and turned: it will sit in its slot, crooked
            L.tilt = f.side * 0.32;
            L.fly = {
              x0: hand.x,
              y0: hand.y,
              vx: (L.sx - hand.x) / T,
              vy: (L.sy - 2 - hand.y - 0.5 * G * T * T) / T,
              a0: L.a,
              a1: L.tilt + Math.PI * 2 * -f.side,
              T,
              t: 0,
            };
            go(f, "toss");
          }
          break;
        }
        case "toss": {
          settle(
            f,
            { ...STAND, lean: 0.3, head: -0.35, hipA: 0.45, kneeA: 0.35, hipB: -0.45, kneeB: 0.1 },
            dt,
            18,
          );
          reachA = handTo({ x: f.x + f.f * 0.55 * H, y: f.y - 1.2 * H }, smooth(f.t / 0.12));
          if (L.mode === "seated") go(f, "watch");
          break;
        }
        case "watch": {
          // it went in, but crooked; a beat, a look at the reader, then off to fix it
          settle(f, { ...STAND, head: -0.35, lean: -0.02 }, dt);
          if (f.t > 0.6 && f.t < 1.1) turnTo(f, 0, dt);
          if (f.t > 1.4) {
            f.ledges = textLedges(window.scrollY, f.floor);
            const goal = f.ledges
              .filter(
                (l) => l.y < L.sy && l.y > L.sy - L.h * 0.9 && l.left < L.sx && l.right > L.sx,
              )
              .sort((a, b) => b.y - a.y)[0];
            const path = goal ? route(f.ledges, f.ledge, goal, H) : null;
            if (path && path.length) {
              f.path = path;
              f.hop = 0;
              f.arc = null;
              go(f, "climb");
            } else {
              // nothing to climb: it will have to do; straighten it with a long-distance glare
              L.tilt = 0;
              go(f, "thumbs");
            }
          }
          break;
        }
        case "climb": {
          const next = f.path[f.hop]!;
          const final = f.hop === f.path.length - 1;
          const landX = final
            ? Math.max(
                next.left + 0.25 * H,
                Math.min(next.right - 0.25 * H, L.sx - f.side * 0.62 * H),
              )
            : Math.max(
                next.left + 0.3 * H,
                Math.min(next.right - 0.3 * H, f.x + Math.sign(L.sx - f.x) * 0.6 * H),
              );
          if (!f.arc) {
            // walk to the take-off point on this ledge, then jump
            const takeoff = Math.max(
              f.ledge.left + 0.2 * H,
              Math.min(f.ledge.right - 0.2 * H, landX - Math.sign(landX - f.x || 1) * 0.5 * H),
            );
            if (Math.abs(takeoff - f.x) > 2 && !walkTo(f, takeoff, 1.6 * H, dt)) break;
            f.vx = 0;
            settle(
              f,
              {
                ...STAND,
                lean: 0.3,
                hipA: 0.8,
                kneeA: 1.3,
                hipB: 0.5,
                kneeB: 1.1,
                shA: -0.6,
                shB: -0.5,
              },
              dt,
              18,
            );
            if (f.t > 0.18) {
              f.arc = arc(f.x, f.y, landX, next.y, 0.45 * H);
              f.f = Math.sign(landX - f.x) || f.f;
              burst(f, f.x, f.y, "dust", 0.35);
              f.t = 0;
            }
            break;
          }
          const a = f.arc;
          a.t = Math.min(a.T, a.t + dt);
          const p = arcAt(a, a.t);
          f.x = p.x;
          f.y = p.y;
          const rising = a.vy + G * a.t < 0;
          settle(
            f,
            rising
              ? {
                  ...STAND,
                  lean: 0.15,
                  head: -0.2,
                  hipA: 1.0,
                  kneeA: 1.6,
                  hipB: 0.5,
                  kneeB: 1.3,
                  shA: 2.4,
                  shB: 2.0,
                }
              : {
                  ...STAND,
                  lean: 0.05,
                  hipA: 0.4,
                  kneeA: 0.4,
                  hipB: 0.1,
                  kneeB: 0.5,
                  shA: 1.2,
                  shB: 0.9,
                },
            dt,
            16,
          );
          if (a.t >= a.T) {
            f.squash.kick(3.5);
            burst(f, f.x, f.y, "dust", 0.45);
            f.ledge = next;
            f.arc = null;
            f.hop++;
            f.t = 0;
            if (f.hop >= f.path.length) go(f, "adjust");
          }
          break;
        }
        case "adjust": {
          // crouch at the letter and push it straight
          turnTo(f, Math.sign(L.sx - f.x) || f.side, dt);
          const k = f.t / 1.3;
          settle(
            f,
            { ...STAND, lean: 0.5, head: 0.45, hipA: 1.0, kneeA: 1.5, hipB: 0.6, kneeB: 1.3 },
            dt,
            10,
          );
          const corner = { x: L.sx - f.f * L.w * 0.45, y: L.sy - L.h * 0.38 };
          reachA = handTo(corner, smooth(k * 3));
          if (k > 0.35 && L.tilt !== 0) {
            L.tilt = 0;
            L.wobble.kick(-6);
          }
          if (k >= 1) {
            const landX = Math.max(30, Math.min(window.innerWidth - 30, f.x - f.side * 1.6 * H));
            f.arc = arc(f.x, f.y, landX, f.floor, 0.4 * H);
            f.f = Math.sign(landX - f.x) || f.f;
            go(f, "down");
          }
          break;
        }
        case "down": {
          const a = f.arc!;
          a.t = Math.min(a.T, a.t + dt);
          const p = arcAt(a, a.t);
          f.x = p.x;
          f.y = p.y;
          const rising = a.vy + G * a.t < 0;
          settle(
            f,
            rising
              ? { ...STAND, hipA: 0.9, kneeA: 1.5, hipB: 0.4, kneeB: 1.2, shA: 2.2, shB: 1.9 }
              : {
                  ...STAND,
                  lean: -0.05,
                  hipA: 0.35,
                  kneeA: 0.3,
                  hipB: -0.1,
                  kneeB: 0.45,
                  shA: 2.6,
                  shB: 2.2,
                },
            dt,
            14,
          );
          if (a.t >= a.T) {
            f.ledge = { left: 0, right: window.innerWidth, y: f.floor };
            f.squash.kick(Math.min(7, a.vy * 0 + 6));
            burst(f, f.x, f.y, "dust", 1.1);
            go(f, "thumbs");
          }
          break;
        }
        case "thumbs": {
          // straight at the reader
          turnTo(f, 0, dt);
          settle(
            f,
            {
              ...STAND,
              lean: 0,
              hipA: 0.14,
              kneeA: 0.05,
              hipB: 0.14,
              kneeB: 0.05,
              shA: 1.35,
              elA: 1.75,
              shB: 0.25,
              elB: 0.25,
              head: -0.05,
            },
            dt,
            10,
          );
          f.thumb = f.t > 0.35;
          if (f.t > 1.6) go(f, "pencil");
          break;
        }
        case "pencil": {
          turnTo(f, f.side, dt);
          const k = f.t / 0.6;
          settle(f, { ...STAND, head: 0.25 }, dt);
          reachA = handTo(
            k < 0.5
              ? { x: f.x + f.f * 0.1 * H, y: f.y - 0.42 * H }
              : { x: f.x + f.f * 0.35 * H, y: f.y - 0.8 * H },
            smooth(k * 3),
          );
          f.pencil = k > 0.5;
          if (k >= 1) {
            const w = 0.62 * H;
            const h = 1.18 * H;
            const x0 = Math.max(
              20,
              Math.min(window.innerWidth - w - 20, f.x + f.f * 0.45 * H - (f.f < 0 ? w : 0)),
            );
            f.door = { x0, y0: f.floor - h, w, h, drawn: 0, theta: 0, alpha: 1 };
            go(f, "draw");
          }
          break;
        }
        case "draw": {
          // up the left post, along the lintel, down the right post; he moves with the pencil
          const door = f.door!;
          door.drawn = clamp01(f.t / 2.6);
          const tip = doorPoint(door, EASE.inOut(door.drawn));
          const body = tip.x - f.side * 0.28 * H;
          walkTo(f, body, 1.5 * H, dt);
          turnTo(f, Math.sign(tip.x - f.x) || f.side, dt);
          const reach = clamp01((f.y - tip.y) / (1.2 * H));
          settle(
            f,
            {
              ...STAND,
              lean: 0.05,
              head: -0.3 * reach + 0.15,
              hipA: 0.15 - 0.5 * (1 - reach) * (tip.y > f.y - 0.5 * H ? 1 : 0),
              kneeA: 0.1 + 1.2 * (tip.y > f.y - 0.4 * H ? 1 : 0),
              hipB: -0.1,
              kneeB: 0.1 + 1.0 * (tip.y > f.y - 0.4 * H ? 1 : 0),
            },
            dt,
            10,
          );
          lift = reach > 0.9 ? 0.04 * H : 0; // on tiptoe for the lintel
          reachA = handTo(tip);
          if (door.drawn >= 1) {
            f.pencil = false;
            go(f, "open");
          }
          break;
        }
        case "open": {
          const door = f.door!;
          // grab the edge and pull it open towards the reader
          const hinge = door.x0;
          walkTo(f, hinge + door.w + 0.3 * H, 1.2 * H, dt);
          turnTo(f, -1, dt);
          settle(f, { ...STAND, lean: -0.12, head: 0.05 }, dt);
          const k = clamp01((f.t - 0.4) / 0.6);
          door.theta = EASE.out(k) * 1.35;
          reachA = handTo(
            { x: hinge + door.w * Math.cos(door.theta), y: door.y0 + door.h * 0.55 },
            smooth((f.t - 0.2) * 4),
          );
          if (f.t > 1.15) go(f, "enterDoor");
          break;
        }
        case "enterDoor": {
          const door = f.door!;
          const inside = door.x0 + door.w * 0.5;
          walkTo(f, inside, 1.1 * H, dt);
          const k = clamp01((door.x0 + door.w - f.x) / (door.w * 0.42));
          f.alpha = 1 - smooth(k);
          if (f.alpha <= 0.02) {
            f.alpha = 0;
            go(f, "shut");
          }
          break;
        }
        case "shut": {
          const door = f.door!;
          door.theta = 1.35 * (1 - EASE.in(clamp01(f.t / 0.35)));
          if (f.t > 0.35 && f.t - dt <= 0.35) burst(f, door.x0 + door.w, f.floor, "dust", 0.5);
          if (f.t > 1.0) go(f, "peek");
          break;
        }
        case "peek": {
          const door = f.door!;
          door.theta = EASE.out(clamp01(f.t / 0.4)) * 1.05;
          f.x = door.x0 + door.w * 0.76;
          f.alpha = 1;
          f.f = 0;
          settle(f, { ...STAND, lean: 0.12 }, dt);
          if (f.t > 0.45) go(f, "bye");
          break;
        }
        case "bye": {
          const door = f.door!;
          door.theta = 1.05;
          f.f = 0;
          settle(f, { ...wave(f.t), lean: 0.12, hipA: 0.14, hipB: 0.14 }, dt, 14);
          if (f.t > 1.8) go(f, "slam");
          break;
        }
        case "slam": {
          const door = f.door!;
          const k = clamp01(f.t / 0.28);
          f.alpha = 1 - smooth(k * 1.5);
          door.theta = 1.05 * (1 - EASE.in(k));
          if (k >= 1 && f.t - dt < 0.28) {
            burst(f, door.x0 + door.w, f.floor, "dust", 0.8);
            knock(L.span.closest("section"), { y: 90 }, 1.4);
          }
          if (f.t > 0.5) go(f, "linger");
          break;
        }
        case "linger": {
          if (f.t > 2.6) go(f, "fade");
          break;
        }
        case "fade": {
          f.door!.alpha = 1 - clamp01(f.t / 0.9);
          if (f.t > 0.9) end();
          return;
        }
      }
      if (!film) return;
      const sq = Math.max(0, f.squash.x);
      const pose =
        sq > 0.01
          ? {
              ...f.pose,
              hipA: f.pose.hipA + 0.5 * sq,
              kneeA: f.pose.kneeA + 0.95 * sq,
              hipB: f.pose.hipB + 0.45 * sq,
              kneeB: f.pose.kneeB + 0.9 * sq,
            }
          : f.pose;
      f.j = solve(pose, d, f.x, f.y, f.f, {
        reachA,
        reachB,
        gaze,
        lift: lift - sq * 0.08 * H,
        pelvisY,
      });
      // a held letter rides in his hand
      if (L.mode === "held" && f.j) {
        L.x = f.j.handA.x;
        L.y = f.j.handA.y - L.h * 0.3;
        L.a += (0 - L.a) * approach(dt, 8);
      }
    };

    const stepLetter = (f: Film, dt: number) => {
      const L = f.letter;
      L.wobble.step(dt);
      if (L.mode === "free") {
        L.vy += G * dt;
        L.x += L.vx * dt;
        L.y += L.vy * dt;
        L.a += L.av * dt;
        const r = Math.min(L.w, L.h) * 0.45;
        if (L.y + r > f.floor) {
          L.y = f.floor - r;
          if (L.vy > 300) burst(f, L.x, f.floor, "dust", Math.min(1, L.vy / 1500));
          L.vy = -L.vy * 0.32;
          L.vx *= 0.7;
          L.av = L.vx / r;
          if (Math.abs(L.vy) < 60) L.vy = 0;
        }
        if (L.x < 10 || L.x > window.innerWidth - 10) {
          L.vx = -L.vx * 0.5;
          L.x = Math.max(10, Math.min(window.innerWidth - 10, L.x));
        }
        // at rest: settle onto a side
        if (L.vy === 0 && Math.abs(L.vx) < 20) {
          const rest = Math.round(L.a / (Math.PI / 2)) * (Math.PI / 2);
          L.a += (rest - L.a) * approach(dt, 6);
          L.av = 0;
        }
      } else if (L.mode === "flying" && L.fly) {
        const fl = L.fly;
        fl.t = Math.min(fl.T, fl.t + dt);
        L.x = fl.x0 + fl.vx * fl.t;
        L.y = fl.y0 + fl.vy * fl.t + 0.5 * G * fl.t * fl.t;
        L.a = lerp(fl.a0, fl.a1, EASE.out(fl.t / fl.T));
        if (fl.t >= fl.T) {
          L.mode = "seated";
          L.x = L.sx + f.side * 2;
          L.y = L.sy - 2;
          L.a = L.tilt;
          L.wobble.kick(10);
          burst(f, L.sx, L.sy, "spark", 0.45);
        }
      } else if (L.mode === "seated") {
        L.a += (L.tilt - L.a) * approach(dt, 10);
        if (L.tilt === 0) {
          L.x += (L.sx - L.x) * approach(dt, 10);
          L.y += (L.sy - L.y) * approach(dt, 10);
        }
      }
      const dx = L.x - L.sx;
      const dy = L.y - L.sy;
      const a = L.a + L.wobble.x * 0.02;
      L.span.style.transform =
        Math.abs(dx) < 0.3 && Math.abs(dy) < 0.3 && Math.abs(a) < 0.002
          ? ""
          : `translate(${dx.toFixed(1)}px, ${dy.toFixed(1)}px) rotate(${a.toFixed(3)}rad)`;
    };

    // ── drawing ──
    const draw = (f: Film) => {
      const sy = window.scrollY;
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(0, 0, cv.width, cv.height);
      ctx.setTransform(dpr, 0, 0, dpr, 0, -sy * dpr);
      const { d, ink } = f;
      const door = f.door;
      // the door: drawn in pencil, a dark doorway behind, the panel swinging towards us
      if (door) {
        ctx.globalAlpha = door.alpha;
        if (door.theta > 0.01) {
          ctx.fillStyle = "rgba(6,8,18,0.92)";
          ctx.fillRect(door.x0, door.y0, door.w, door.h);
        }
        ctx.globalAlpha = 1;
      }
      // he is inside the doorway while peeking and waving
      const inDoor = door && (f.st === "peek" || f.st === "bye" || f.st === "slam");
      if (f.j) {
        if (inDoor && door) {
          ctx.save();
          ctx.beginPath();
          ctx.rect(door.x0, door.y0, door.w, door.h);
          ctx.clip();
        }
        if (f.st !== "fall" && f.alpha > 0.05 && !inDoor) {
          const air = clamp01((f.ledge.y - Math.max(f.j.footA.y, f.j.footB.y)) / (2 * f.H));
          drawShadow(ctx, f.x, f.ledge.y, d, air, ink, f.alpha);
        }
        if (f.alpha > 0.01)
          drawBody(
            ctx,
            f.j,
            d,
            inDoor ? { ...ink, ink: "#eef1ff", page: "rgba(6,8,18,0.92)" } : ink,
            {
              alpha: f.alpha,
              thumb: f.thumb,
            },
          );
        if (inDoor) ctx.restore();
        // pencil in hand
        if (f.pencil) {
          const h = f.j.handA;
          const e = f.j.elbowA;
          const len = Math.hypot(h.x - e.x, h.y - e.y) || 1;
          ctx.strokeStyle = ink.accent;
          ctx.lineWidth = 0.035 * f.H;
          ctx.lineCap = "round";
          ctx.beginPath();
          ctx.moveTo(h.x, h.y);
          ctx.lineTo(
            h.x + ((h.x - e.x) / len) * 0.14 * f.H,
            h.y + ((h.y - e.y) / len) * 0.14 * f.H,
          );
          ctx.stroke();
        }
      }
      if (door) {
        ctx.globalAlpha = door.alpha;
        ctx.strokeStyle = ink.ink;
        ctx.lineCap = "round";
        ctx.lineJoin = "round";
        ctx.lineWidth = 0.032 * f.H;
        // the drawn frame, as far as the pencil has got, a touch hand-wobbly
        ctx.beginPath();
        const n = 60;
        for (let i = 0; i <= n; i++) {
          const k = (i / n) * EASE.inOut(door.drawn);
          const p = doorPoint(door, k);
          const wob = Math.sin(k * 40) * 0.6;
          if (i === 0) ctx.moveTo(p.x + wob, p.y);
          else ctx.lineTo(p.x + wob, p.y + wob * 0.3);
        }
        ctx.stroke();
        // the panel: hinged on the left, its free edge swinging out towards the reader
        if (door.drawn >= 1) {
          const cos = Math.cos(door.theta);
          const sin = Math.sin(door.theta);
          const xf = door.x0 + door.w * cos;
          const grow = 1 + 0.2 * sin;
          const cy = door.y0 + door.h / 2;
          ctx.beginPath();
          ctx.moveTo(door.x0, door.y0);
          ctx.lineTo(xf, cy - (door.h / 2) * grow);
          ctx.lineTo(xf, cy + (door.h / 2) * grow);
          ctx.lineTo(door.x0, door.y0 + door.h);
          ctx.closePath();
          ctx.fillStyle = ink.page;
          ctx.fill();
          ctx.stroke();
          ctx.fillStyle = ink.ink;
          ctx.beginPath();
          ctx.arc(
            door.x0 + door.w * cos * 0.82,
            cy + 0.05 * door.h,
            0.03 * f.H * (1 + 0.3 * sin),
            0,
            Math.PI * 2,
          );
          ctx.fill();
        }
        ctx.globalAlpha = 1;
      }
      // the rope
      if (f.j && f.rope !== "none") {
        const hand = f.j.handA;
        ctx.strokeStyle = ink.ink;
        ctx.lineWidth = Math.max(1.6, 0.022 * f.H);
        ctx.lineCap = "round";
        const L = f.letter;
        let end: Vec = f.ropeEnd;
        if (f.rope === "hooked" || (f.st === "swing" && f.rope !== "slack"))
          end = { x: L.sx, y: L.sy - L.h * 0.1 };
        if (f.rope === "slack") end = { x: L.x, y: L.y };
        if (f.rope === "coil") {
          ctx.beginPath();
          ctx.ellipse(hand.x, hand.y + 0.05 * f.H, 0.07 * f.H, 0.09 * f.H, 0.4, 0, Math.PI * 2);
          ctx.stroke();
        } else {
          const span = Math.hypot(end.x - hand.x, end.y - hand.y);
          const slack =
            f.rope === "slack"
              ? Math.max(0, f.ropeLen - span)
              : f.rope === "flying"
                ? 40
                : f.rope === "reel"
                  ? 25
                  : 0;
          ctx.beginPath();
          ctx.moveTo(hand.x, hand.y);
          ctx.quadraticCurveTo(
            (hand.x + end.x) / 2,
            (hand.y + end.y) / 2 + slack * 0.6,
            end.x,
            end.y,
          );
          ctx.stroke();
          if (f.rope === "whirl" || f.rope === "flying") {
            ctx.beginPath();
            ctx.ellipse(end.x, end.y, 0.2 * f.H, 0.07 * f.H, 0, 0, Math.PI * 2);
            ctx.stroke();
          } else if (f.rope === "hooked" || f.st === "swing") {
            ctx.beginPath();
            ctx.ellipse(L.sx, L.sy - L.h * 0.1, L.w * 0.42, L.h * 0.2, 0, 0, Math.PI * 2);
            ctx.stroke();
          }
        }
      }
      // sparks and dust
      for (const q of f.fx) {
        const k = 1 - q.age / q.life;
        if (q.kind === "spark") {
          ctx.globalAlpha = k;
          ctx.strokeStyle = ink.accent;
          ctx.lineWidth = 2.4;
          const sp = Math.hypot(q.vx, q.vy) || 1;
          ctx.beginPath();
          ctx.moveTo(q.x, q.y);
          ctx.lineTo(q.x - (q.vx / sp) * 12 * k, q.y - (q.vy / sp) * 12 * k);
          ctx.stroke();
        } else {
          ctx.globalAlpha = 0.28 * k;
          ctx.fillStyle = ink.ink;
          ctx.beginPath();
          ctx.arc(q.x, q.y, 4 + 7 * (1 - k), 0, Math.PI * 2);
          ctx.fill();
        }
      }
      ctx.globalAlpha = 1;
      cv.dataset.stage = f.st;
    };

    // particles advance with the film, then the script runs
    const stepAll = (f: Film, dt: number) => {
      for (const q of f.fx) {
        q.age += dt;
        q.vx *= Math.exp(-dt * (q.kind === "spark" ? 6 : 4));
        q.vy =
          q.vy * Math.exp(-dt * (q.kind === "spark" ? 6 : 3)) +
          (q.kind === "spark" ? 1000 * dt : 0);
        q.x += q.vx * dt;
        q.y += q.vy * dt;
      }
      f.fx = f.fx.filter((q) => q.age < q.life);
      step(f, dt);
    };

    return () => {
      if (film) end();
      cancelAnimationFrame(raf);
      unregister();
      window.removeEventListener("resize", onResize);
    };
  }, []);

  return (
    <canvas
      ref={canvas}
      aria-hidden
      className="pointer-events-none fixed inset-0 z-40"
      style={{ width: "100vw", height: "100vh" }}
    />
  );
}

/** A point along the door outline: up the left post, along the lintel, down the right post. */
function doorPoint(door: { x0: number; y0: number; w: number; h: number }, k: number): Vec {
  const total = 2 * door.h + door.w;
  let s = k * total;
  if (s <= door.h) return { x: door.x0, y: door.y0 + door.h - s };
  s -= door.h;
  if (s <= door.w) return { x: door.x0 + s, y: door.y0 };
  s -= door.w;
  return { x: door.x0 + door.w, y: door.y0 + s };
}

function blend(a: Joints, b: Joints, k: number): Joints {
  const o = { ...b };
  for (const key of [
    "head",
    "chest",
    "shoulder",
    "pelvis",
    "elbowA",
    "handA",
    "elbowB",
    "handB",
    "kneeA",
    "footA",
    "kneeB",
    "footB",
  ] as const) {
    o[key] = { x: a[key].x + (b[key].x - a[key].x) * k, y: a[key].y + (b[key].y - a[key].y) * k };
  }
  return o;
}

function useMotionAllowed() {
  return useSyncExternalStore(
    (cb) => {
      const m = window.matchMedia("(prefers-reduced-motion: reduce)");
      m.addEventListener("change", cb);
      return () => m.removeEventListener("change", cb);
    },
    () => !window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    () => false,
  );
}

/** The idle film, unless the layer is off or the visitor asked for less motion. */
export function Interlude() {
  const allowed = useMotionAllowed();
  return FIGURES_ON && allowed ? <InterludeLayer /> : null;
}
