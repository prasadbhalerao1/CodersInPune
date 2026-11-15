/**
 * Shared kit for the idle films: an Actor (a figure with momentum, keyed and procedural poses,
 * squash on landings, whole-body rotation for flips), ballistic arcs, particles, a canvas that
 * follows the page, and helpers that wrap page text in spans for a film and put it back after.
 */

import { drawBody, drawShadow, type Ink } from "./canvas";
import { Spring } from "./physics";
import {
  STAND,
  approach,
  clamp01,
  dims,
  gait,
  mix,
  runLift,
  solve,
  stride,
  type Dims,
  type Joints,
  type Pose,
  type Reach,
  type Vec,
} from "./rig";

export const G = 2600;
export const lerp = (a: number, b: number, k: number) => a + (b - a) * k;

// ── ballistic arcs ──────────────────────────────────────────────────────────────────────

export type Arc = {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  vx: number;
  vy: number;
  T: number;
  t: number;
};

/** A jump from (x0, y0) to (x1, y1) peaking `over` above the higher end (y grows downwards). */
export function arc(x0: number, y0: number, x1: number, y1: number, over: number, g = G): Arc {
  const top = Math.min(y0, y1) - over;
  const vy = -Math.sqrt(2 * g * (y0 - top));
  const T = -vy / g + Math.sqrt((2 * (y1 - top)) / g);
  return { x0, y0, x1, y1, vx: (x1 - x0) / T, vy, T, t: 0 };
}
export const arcAt = (a: Arc, t: number, g = G): Vec => ({
  x: a.x0 + a.vx * t,
  y: a.y0 + a.vy * t + 0.5 * g * t * t,
});
export const arcRising = (a: Arc, g = G) => a.vy + g * a.t < 0;

// ── poses used across films ─────────────────────────────────────────────────────────────

export const CROUCH: Pose = {
  ...STAND,
  lean: 0.32,
  head: -0.15,
  hipA: 0.95,
  kneeA: 1.6,
  hipB: 0.6,
  kneeB: 1.35,
  shA: -0.5,
  elA: 0.4,
  shB: -0.4,
  elB: 0.4,
};
export const AIR_UP: Pose = {
  ...STAND,
  lean: 0.1,
  head: -0.2,
  hipA: 1.0,
  kneeA: 1.7,
  hipB: 0.5,
  kneeB: 1.4,
  shA: 2.4,
  elA: 0.4,
  shB: 2.0,
  elB: 0.5,
};
export const AIR_DOWN: Pose = {
  ...STAND,
  lean: -0.05,
  head: 0.15,
  hipA: 0.35,
  kneeA: 0.35,
  hipB: -0.1,
  kneeB: 0.5,
  shA: 2.5,
  elA: 0.3,
  shB: 2.1,
  elB: 0.4,
};
export const FRONT: Pose = {
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
export const SHRUG: Pose = { ...FRONT, head: 0.12, shA: 0.75, elA: -0.9, shB: 0.75, elB: -0.9 };
export const BOW: Pose = {
  ...FRONT,
  lean: 0.85,
  head: 0.35,
  shA: 0.2,
  elA: 0.6,
  shB: -0.2,
  elB: 0.6,
};
export const THUMB: Pose = { ...FRONT, shA: 1.35, elA: 1.75, shB: 0.25, elB: 0.25, head: -0.05 };

// ── the actor ───────────────────────────────────────────────────────────────────────────

export type Shot = { reachA?: Reach; reachB?: Reach; gaze?: Vec; lift?: number; pelvisY?: number };

export class Actor {
  H: number;
  d: Dims;
  x: number;
  y: number;
  f: number;
  vx = 0;
  ph = 0;
  pose: Pose = STAND;
  squash = new Spring(300, 15);
  alpha = 1;
  rot = 0;
  thumb = false;
  j: Joints | null = null;
  arc: Arc | null = null;
  constructor(H: number, x: number, y: number, f = 1) {
    this.H = H;
    this.d = dims(H);
    this.x = x;
    this.y = y;
    this.f = f;
  }
  settle(p: Pose, dt: number, rate = 9) {
    this.pose = mix(this.pose, p, approach(dt, rate));
  }
  turnTo(target: number, dt: number, rate = 10) {
    this.f += (target - this.f) * approach(dt, rate);
  }
  /** Walk or run towards x with momentum. True once stopped there. */
  walkTo(tx: number, speed: number, dt: number) {
    const H = this.H;
    const gap = tx - this.x;
    const stop = (this.vx * this.vx) / (2 * 9 * H);
    const want = Math.abs(gap) < 2 ? 0 : Math.abs(gap) <= stop ? 0 : Math.sign(gap) * speed;
    const dv = want - this.vx;
    this.vx +=
      Math.sign(dv) *
      Math.min(Math.abs(dv), (Math.abs(want) > Math.abs(this.vx) ? 7 : 11) * H * dt);
    if (
      Math.abs(gap) < Math.abs(this.vx * dt) ||
      (Math.abs(gap) < 2 && Math.abs(this.vx) < 0.2 * H)
    ) {
      this.x = tx;
      this.vx = 0;
      return true;
    }
    this.x += this.vx * dt;
    if (Math.abs(this.vx) > 0.1 * H) this.f = Math.sign(this.vx);
    const run = clamp01((Math.abs(this.vx) - 1.3 * H) / (3.4 * H));
    this.ph += (2 * Math.PI * Math.abs(this.vx) * dt) / stride(run, H);
    this.pose = mix(this.pose, gait(this.ph, run), approach(dt, 20));
    return false;
  }
  /** Run at a constant speed in the facing direction (no braking). */
  run(speed: number, dt: number) {
    const H = this.H;
    const dv = speed - this.vx;
    this.vx += Math.sign(dv) * Math.min(Math.abs(dv), 14 * H * dt);
    this.x += this.vx * dt;
    if (Math.abs(this.vx) > 0.1 * H) this.f = Math.sign(this.vx);
    const r = clamp01((Math.abs(this.vx) - 1.3 * H) / (3.4 * H));
    this.ph += (2 * Math.PI * Math.abs(this.vx) * dt) / stride(r, H);
    this.pose = mix(this.pose, gait(this.ph, r), approach(dt, 22));
  }
  /** Fly the current arc; returns true on landing (with a squash kick and the landing speed). */
  fly(dt: number): number | null {
    const a = this.arc;
    if (!a) return null;
    a.t = Math.min(a.T, a.t + dt);
    const p = arcAt(a, a.t);
    this.x = p.x;
    this.y = p.y;
    this.settle(arcRising(a) ? AIR_UP : AIR_DOWN, dt, 14);
    if (a.t >= a.T) {
      const speed = a.vy + G * a.T;
      this.arc = null;
      this.squash.kick(Math.min(7, speed / 140));
      return speed;
    }
    return null;
  }
  jump(x1: number, y1: number, over: number) {
    this.arc = arc(this.x, this.y, x1, y1, over);
    if (Math.abs(x1 - this.x) > 2) this.f = Math.sign(x1 - this.x);
  }
  /** Solve the joints for this frame. */
  pose2joints(dt: number, shot: Shot = {}, running = 0) {
    this.squash.step(dt);
    const sq = Math.max(0, this.squash.x);
    const p =
      sq > 0.01
        ? {
            ...this.pose,
            hipA: this.pose.hipA + 0.5 * sq,
            kneeA: this.pose.kneeA + 0.95 * sq,
            hipB: this.pose.hipB + 0.45 * sq,
            kneeB: this.pose.kneeB + 0.9 * sq,
            lean: this.pose.lean + 0.12 * sq,
          }
        : this.pose;
    const lift =
      (shot.lift ?? 0) -
      sq * 0.08 * this.H +
      (running ? runLift(this.ph, running, this.H, p, this.d) : 0);
    this.j = solve(p, this.d, this.x, this.y, this.f, {
      reachA: shot.reachA,
      reachB: shot.reachB,
      gaze: shot.gaze,
      lift,
      pelvisY: shot.pelvisY,
    });
    return this.j;
  }
  draw(ctx: CanvasRenderingContext2D, ink: Ink, groundY?: number, override?: Joints) {
    const j = override ?? this.j;
    if (!j || this.alpha < 0.01) return;
    if (groundY !== undefined && !override) {
      const air = clamp01((groundY - Math.max(j.footA.y, j.footB.y)) / (2 * this.H));
      drawShadow(ctx, (j.footA.x + j.footB.x) / 2, groundY, this.d, air, ink, this.alpha);
    }
    if (this.rot) {
      ctx.save();
      ctx.translate(j.pelvis.x, j.pelvis.y - 0.15 * this.H);
      ctx.rotate(this.rot);
      ctx.translate(-j.pelvis.x, -(j.pelvis.y - 0.15 * this.H));
    }
    drawBody(ctx, j, this.d, ink, { alpha: this.alpha, thumb: this.thumb });
    if (this.rot) ctx.restore();
  }
}

export const reach = (target: Vec, w = 1, bend = -1): Reach => ({ target, w, bend });

/**
 * Hang the actor from a hand point: the body hangs along `theta` (radians from straight down,
 * positive towards +x), legs as given. Sets x and the pose; returns the pelvis height to pass
 * as `pelvisY`.
 */
export function hang(a: Actor, hand: Vec, theta: number, legs: Partial<Pose> = {}) {
  const d = a.d;
  const dir = { x: Math.sin(theta), y: Math.cos(theta) };
  const arm = (d.upper + d.fore) * 0.9;
  const chest = { x: hand.x + dir.x * arm, y: hand.y + dir.y * arm };
  const pelvis = { x: chest.x + dir.x * d.torso, y: chest.y + dir.y * d.torso };
  const fs = a.f < 0 ? -1 : 1;
  const lean = Math.atan2(-dir.x * fs, dir.y);
  const tilt = Math.atan2(dir.x * fs, dir.y);
  a.x = pelvis.x;
  a.pose = {
    ...a.pose,
    lean,
    head: -lean * 0.4 - 0.1,
    hipA: tilt + (legs.hipA ?? 0.3),
    kneeA: legs.kneeA ?? 0.45,
    hipB: tilt + (legs.hipB ?? 0.08),
    kneeB: legs.kneeB ?? 0.3,
  };
  return pelvis.y;
}

// ── particles ───────────────────────────────────────────────────────────────────────────

type P = {
  x: number;
  y: number;
  vx: number;
  vy: number;
  age: number;
  life: number;
  kind: "spark" | "dust" | "bit" | "ring";
  size: number;
  spin: number;
};

export class Fx {
  ps: P[] = [];
  seed = 4242;
  rnd() {
    let x = this.seed;
    x ^= x << 13;
    x ^= x >>> 17;
    x ^= x << 5;
    this.seed = x >>> 0;
    return (this.seed % 10000) / 10000;
  }
  sparks(x: number, y: number, power = 1, angle = -Math.PI / 2, spread = Math.PI * 2) {
    const n = Math.round(8 + 8 * power);
    for (let i = 0; i < n; i++) {
      const a = angle + (this.rnd() - 0.5) * spread;
      const v = (300 + 500 * this.rnd()) * (0.6 + 0.5 * power);
      this.ps.push({
        x,
        y,
        vx: Math.cos(a) * v,
        vy: Math.sin(a) * v,
        age: 0,
        life: 0.3,
        kind: "spark",
        size: 10,
        spin: 0,
      });
    }
  }
  dust(x: number, y: number, power = 1) {
    const n = Math.round(4 + 6 * power);
    for (let i = 0; i < n; i++) {
      const side = i % 2 ? 1 : -1;
      const v = (50 + 140 * this.rnd()) * (0.6 + 0.6 * power);
      this.ps.push({
        x: x + side * 4 * this.rnd(),
        y,
        vx: side * v,
        vy: -(20 + 60 * this.rnd()),
        age: 0,
        life: 0.6,
        kind: "dust",
        size: 3 + 5 * this.rnd() * power,
        spin: 0,
      });
    }
  }
  /** Bits of something (balloon rubber, paper): fly out, tumble, fall. */
  bits(x: number, y: number, n: number, power = 1) {
    for (let i = 0; i < n; i++) {
      const a = this.rnd() * Math.PI * 2;
      const v = (200 + 400 * this.rnd()) * power;
      this.ps.push({
        x,
        y,
        vx: Math.cos(a) * v,
        vy: Math.sin(a) * v - 200,
        age: 0,
        life: 0.9 + 0.5 * this.rnd(),
        kind: "bit",
        size: 4 + 5 * this.rnd(),
        spin: (this.rnd() - 0.5) * 20,
      });
    }
  }
  ring(x: number, y: number, size: number) {
    this.ps.push({ x, y, vx: 0, vy: 0, age: 0, life: 0.35, kind: "ring", size, spin: 0 });
  }
  step(dt: number) {
    for (const q of this.ps) {
      q.age += dt;
      if (q.kind === "spark") {
        q.vx *= Math.exp(-dt * 6);
        q.vy = q.vy * Math.exp(-dt * 6) + 1000 * dt;
      } else if (q.kind === "dust") {
        q.vx *= Math.exp(-dt * 4);
        q.vy *= Math.exp(-dt * 3);
      } else if (q.kind === "bit") {
        q.vx *= Math.exp(-dt * 2.5);
        q.vy = q.vy * Math.exp(-dt * 2.5) + 900 * dt;
      }
      q.x += q.vx * dt;
      q.y += q.vy * dt;
    }
    this.ps = this.ps.filter((q) => q.age < q.life);
  }
  draw(ctx: CanvasRenderingContext2D, ink: Ink) {
    for (const q of this.ps) {
      const k = 1 - q.age / q.life;
      if (q.kind === "spark") {
        const sp = Math.hypot(q.vx, q.vy) || 1;
        ctx.globalAlpha = k;
        ctx.strokeStyle = ink.accent;
        ctx.lineWidth = 2.4;
        ctx.lineCap = "round";
        ctx.beginPath();
        ctx.moveTo(q.x, q.y);
        ctx.lineTo(q.x - (q.vx / sp) * q.size * k, q.y - (q.vy / sp) * q.size * k);
        ctx.stroke();
      } else if (q.kind === "dust") {
        ctx.globalAlpha = 0.28 * k;
        ctx.fillStyle = ink.ink;
        ctx.beginPath();
        ctx.arc(q.x, q.y, q.size * (1 + 1.4 * (1 - k)), 0, Math.PI * 2);
        ctx.fill();
      } else if (q.kind === "bit") {
        ctx.globalAlpha = Math.min(1, k * 2);
        ctx.fillStyle = ink.accent;
        ctx.save();
        ctx.translate(q.x, q.y);
        ctx.rotate(q.age * q.spin);
        ctx.fillRect(-q.size / 2, -q.size / 4, q.size, q.size / 2);
        ctx.restore();
      } else {
        ctx.globalAlpha = 0.9 * k;
        ctx.strokeStyle = ink.accent;
        ctx.lineWidth = 3 * k + 0.5;
        ctx.beginPath();
        ctx.arc(q.x, q.y, q.size * (0.4 + 0.9 * (1 - k)), 0, Math.PI * 2);
        ctx.stroke();
      }
    }
    ctx.globalAlpha = 1;
  }
}

// ── the canvas ──────────────────────────────────────────────────────────────────────────

/** A full-viewport canvas drawn in document coordinates (or fixed, for films on fixed chrome). */
export function stageCanvas(cv: HTMLCanvasElement) {
  const ctx = cv.getContext("2d")!;
  let dpr = 1;
  const fit = () => {
    dpr = Math.min(2, window.devicePixelRatio || 1);
    cv.width = Math.round(window.innerWidth * dpr);
    cv.height = Math.round(window.innerHeight * dpr);
  };
  fit();
  return {
    ctx,
    fit,
    /** Clear and set up to draw in document space (or viewport space with `fixed`). */
    begin(fixed = false) {
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(0, 0, cv.width, cv.height);
      ctx.setTransform(dpr, 0, 0, dpr, 0, fixed ? 0 : -window.scrollY * dpr);
    },
    clear() {
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(0, 0, cv.width, cv.height);
    },
  };
}

// ── page text ───────────────────────────────────────────────────────────────────────────

/** Wrap each word of an element's text in an inline-block span. Returns the spans and an undo. */
export function wrapWords(el: HTMLElement) {
  const texts: Text[] = [];
  const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
  let n: Node | null;
  while ((n = walker.nextNode())) texts.push(n as Text);
  const spans: HTMLSpanElement[] = [];
  const undo: (() => void)[] = [];
  for (const t of texts) {
    const parent = t.parentNode!;
    const parts = t.data.split(/(\s+)/);
    if (parts.length < 2 && !t.data.trim()) continue;
    const frag = document.createDocumentFragment();
    const made: Node[] = [];
    for (const part of parts) {
      if (!part) continue;
      if (/^\s+$/.test(part)) {
        const s = document.createTextNode(part);
        frag.appendChild(s);
        made.push(s);
      } else {
        const s = document.createElement("span");
        s.textContent = part;
        s.style.display = "inline-block";
        s.setAttribute("data-film-word", "");
        frag.appendChild(s);
        made.push(s);
        spans.push(s);
      }
    }
    parent.insertBefore(frag, t);
    parent.removeChild(t);
    undo.push(() => {
      const first = made[0];
      if (!first || !first.parentNode) return;
      first.parentNode.insertBefore(t, first);
      for (const m of made) m.parentNode?.removeChild(m);
    });
  }
  return {
    spans,
    restore: () => {
      for (const u of undo.reverse()) u();
      el.normalize();
    },
  };
}

/** Wrap one character of a text node in an inline-block span. */
export function wrapChar(node: Text, index: number) {
  const parent = node.parentNode!;
  const letter = node.splitText(index);
  letter.splitText(1);
  const span = document.createElement("span");
  span.style.display = "inline-block";
  span.setAttribute("data-film-letter", "");
  parent.insertBefore(span, letter);
  span.appendChild(letter);
  return {
    span,
    restore: () => {
      if (!span.isConnected) return;
      span.style.transform = "";
      span.replaceWith(letter);
      parent.normalize();
    },
  };
}

/** Visible text characters in headings matching `chars`, with room below them. */
export function findChars(chars: string, minRoomBelow: number, floor: number) {
  const sy = window.scrollY;
  const out: { node: Text; index: number; rect: DOMRect }[] = [];
  const range = document.createRange();
  for (const h of document.querySelectorAll<HTMLElement>("main h2, main h1")) {
    if (parseFloat(getComputedStyle(h).fontSize) < 36) continue;
    const box = h.getBoundingClientRect();
    if (box.top < 100 || box.bottom > window.innerHeight - 40) continue;
    const walker = document.createTreeWalker(h, NodeFilter.SHOW_TEXT);
    let n: Node | null;
    while ((n = walker.nextNode())) {
      const t = n as Text;
      for (let i = 0; i < t.data.length; i++) {
        if (!chars.includes(t.data[i]!)) continue;
        range.setStart(t, i);
        range.setEnd(t, i + 1);
        const rect = range.getBoundingClientRect();
        if (rect.width < 8 || rect.top < 110) continue;
        if (floor - (rect.bottom + sy) < minRoomBelow) continue;
        out.push({ node: t, index: i, rect });
      }
    }
  }
  return out;
}

/** The visible glass card tops, as ledges in document space. */
export function cardTops(minY: number, maxY: number) {
  const sy = window.scrollY;
  const out: { left: number; right: number; y: number; el: HTMLElement }[] = [];
  for (const el of document.querySelectorAll<HTMLElement>(".glass, .glass-dark, .glass-clear")) {
    if (el.closest("header")) continue;
    const r = el.getBoundingClientRect();
    const y = r.top + sy;
    if (r.width < 160 || y < minY || y > maxY) continue;
    out.push({ left: r.left + 6, right: r.right - 6, y, el });
  }
  return out;
}

export { STAND, clamp01, mix, approach };
export type { Ink, Joints, Pose, Vec };
