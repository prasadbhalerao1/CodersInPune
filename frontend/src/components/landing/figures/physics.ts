/**
 * The feel layer: momentum, gravity, impacts. Small, deterministic, frame-rate independent
 * (sub-stepped), and cheap enough to run for every figure on screen.
 *
 * - Spring: a damped spring. Anything that should overshoot and settle (a shoved button, a card
 *   landing, a knee taking a landing) is one.
 * - Body: a figure's root. It accelerates towards where it wants to be instead of teleporting
 *   there, falls under gravity, and reports a landing with its impact speed.
 * - knock(): an impulse on a real page element. The element recoils on its own springs through
 *   the CSS `translate` and `rotate` properties, which compose with whatever `transform` a scene
 *   already sets, so impacts layer on top of choreography instead of fighting it.
 */

import { clamp01, type Pose } from "./rig";

const SUB = 1 / 240;

export class Spring {
  x = 0;
  v = 0;
  constructor(
    /** Stiffness: higher is snappier. */
    public k = 260,
    /** Damping: lower wobbles longer. */
    public c = 14,
  ) {}
  step(dt: number, target = 0) {
    let t = dt;
    while (t > 0) {
      const h = Math.min(SUB, t);
      const a = this.k * (target - this.x) - this.c * this.v;
      this.v += a * h;
      this.x += this.v * h;
      t -= h;
    }
    return this.x;
  }
  kick(dv: number) {
    this.v += dv;
  }
  get resting() {
    return Math.abs(this.x) < 0.01 && Math.abs(this.v) < 0.05;
  }
}

export type Landing = { speed: number };

/**
 * A figure's root in stage pixels: x along the ground, y as height above it (up is positive).
 * `squash` is the knees taking a landing (0 at rest, up to ~1), `ax` the acceleration of the last
 * step, which the pose turns into lean.
 */
export class Body {
  vx = 0;
  vy = 0;
  y = 0;
  ax = 0;
  grounded = true;
  readonly squash = new Spring(320, 16);
  constructor(
    public x = 0,
    /** Pixels per second squared. */
    public gravity = 2600,
  ) {}

  /**
   * Move towards `target` with momentum: accelerate up to `maxSpeed`, then brake in time to
   * stop on the mark. Returns true once settled there.
   */
  seek(target: number, maxSpeed: number, accel: number, dt: number) {
    const gap = target - this.x;
    const stopDist = (this.vx * this.vx) / (2 * accel);
    const dir = Math.sign(gap);
    let want = 0;
    if (Math.abs(gap) > 0.5) want = Math.abs(gap) <= stopDist ? 0 : dir * maxSpeed;
    // braking is harder than accelerating: feet dig in
    const a =
      Math.sign(want - this.vx) === Math.sign(this.vx) || this.vx === 0 ? accel : accel * 1.6;
    const before = this.vx;
    const dv = want - this.vx;
    this.vx += Math.sign(dv) * Math.min(Math.abs(dv), a * dt);
    // never overshoot the mark at low speed
    if (Math.abs(gap) < Math.abs(this.vx * dt)) {
      this.x = target;
      this.vx = 0;
    } else {
      this.x += this.vx * dt;
    }
    this.ax = dt > 0 ? (this.vx - before) / dt : 0;
    return Math.abs(target - this.x) < 0.5 && Math.abs(this.vx) < 1;
  }

  /** Leave the ground with an upward speed (px/s). */
  jump(speed: number, vx = this.vx) {
    if (!this.grounded) return;
    this.grounded = false;
    this.vy = speed;
    this.vx = vx;
  }

  /** Advance gravity and the knees. Returns the landing, if one happened this step. */
  step(dt: number): Landing | null {
    this.squash.step(dt);
    if (this.grounded) return null;
    this.vy -= this.gravity * dt;
    this.y += this.vy * dt;
    this.x += this.vx * dt;
    if (this.y <= 0 && this.vy <= 0) {
      const speed = -this.vy;
      this.y = 0;
      this.vy = 0;
      this.grounded = true;
      this.vx *= 0.35; // friction takes most of the run-on
      this.squash.kick(Math.min(9, speed / 120));
      return { speed };
    }
    return null;
  }
}

/**
 * Turn a body's state into pose: lean into acceleration, lean back to brake, tuck in the air,
 * and bend the knees under a landing.
 */
export function feel(p: Pose, body: Body, H: number, facing: number): Pose {
  const along = facing === 0 ? 0 : body.ax * Math.sign(facing);
  const lean = Math.max(-0.35, Math.min(0.35, along / (14 * H)));
  const sq = Math.max(0, body.squash.x);
  const air = body.grounded ? 0 : clamp01(body.vy / (6 * H));
  const fall = body.grounded ? 0 : clamp01(-body.vy / (6 * H));
  return {
    ...p,
    lean: p.lean + lean + 0.18 * sq,
    head: p.head - 0.5 * lean - 0.12 * sq,
    hipA: p.hipA + 0.55 * sq + 0.5 * air - 0.15 * fall,
    kneeA: p.kneeA + 1.0 * sq + 0.9 * air + 0.2 * fall,
    hipB: p.hipB + 0.45 * sq + 0.35 * air - 0.1 * fall,
    kneeB: p.kneeB + 0.95 * sq + 0.8 * air + 0.2 * fall,
    shA: p.shA + 0.3 * fall,
    shB: p.shB + 0.3 * fall,
  };
}

/** How far the hips drop when the knees take a landing. */
export const crouch = (body: Body, H: number) => Math.max(0, body.squash.x) * 0.09 * H;

// ── impacts on real page elements ───────────────────────────────────────────────────────

type Shake = { x: Spring; y: Spring; r: Spring };
const live = new Map<HTMLElement, Shake>();
let raf = 0;
let last = 0;

function tick(now: number) {
  const dt = last ? Math.min(0.05, (now - last) / 1000) : 0;
  last = now;
  for (const [el, s] of live) {
    s.x.step(dt);
    s.y.step(dt);
    s.r.step(dt);
    if (s.x.resting && s.y.resting && s.r.resting) {
      el.style.removeProperty("translate");
      el.style.removeProperty("rotate");
      live.delete(el);
      continue;
    }
    el.style.translate = `${s.x.x.toFixed(2)}px ${s.y.x.toFixed(2)}px`;
    el.style.rotate = `${s.r.x.toFixed(3)}deg`;
  }
  raf = live.size ? requestAnimationFrame(tick) : 0;
  if (!raf) last = 0;
}

/**
 * Hit a page element: it recoils by the given velocity (px/s, and deg/s for spin) and rings
 * back to rest on springs. `stiff` tunes how heavy it feels (lower is heavier and wobblier).
 */
export function knock(
  el: HTMLElement | null,
  v: { x?: number; y?: number; r?: number },
  stiff = 1,
) {
  if (!el || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  let s = live.get(el);
  if (!s) {
    s = {
      x: new Spring(420 * stiff, 16 * Math.sqrt(stiff)),
      y: new Spring(420 * stiff, 16 * Math.sqrt(stiff)),
      r: new Spring(380 * stiff, 13 * Math.sqrt(stiff)),
    };
    live.set(el, s);
  }
  s.x.kick(v.x ?? 0);
  s.y.kick(v.y ?? 0);
  s.r.kick(v.r ?? 0);
  if (!raf) raf = requestAnimationFrame(tick);
}
