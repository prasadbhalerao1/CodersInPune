/**
 * A Verlet ragdoll: one particle per joint, bones as distance constraints, a few minimum
 * distances as joint limits (a knee cannot fold flat, the head stays off the hips). Collides with
 * one-way platforms (the top edges of page elements) and the walls, floor and ceiling of the
 * viewport, with friction and a little bounce. Reports impacts so whatever was hit can react.
 * Sub-stepped at 240 Hz so a hard throw cannot tunnel through a card.
 */

import type { Dims, Joints, Vec } from "./rig";

export type Plat = { el: HTMLElement | null; left: number; right: number; top: number };
export type Bounds = { left: number; right: number; ceil: number; floor: number };

type P = { x: number; y: number; px: number; py: number; r: number; pinned: boolean };

const NAMES = [
  "head",
  "chest",
  "pelvis",
  "elbowA",
  "handA",
  "elbowB",
  "handB",
  "kneeA",
  "footA",
  "kneeB",
  "footB",
] as const;
type Name = (typeof NAMES)[number];
const I = Object.fromEntries(NAMES.map((n, i) => [n, i])) as Record<Name, number>;

type C = { a: number; b: number; len: number; min?: boolean; stiff: number };

const SUB = 1 / 240;
const GRAVITY = 2600;

export type Impact = { x: number; y: number; speed: number; plat: Plat | null };

export class Ragdoll {
  ps: P[];
  cs: C[];
  pin: number | null = null;
  pinAt: Vec = { x: 0, y: 0 };
  private d: Dims;

  constructor(d: Dims) {
    this.d = d;
    const limb = d.wThigh / 2;
    this.ps = NAMES.map((n) => ({
      x: 0,
      y: 0,
      px: 0,
      py: 0,
      r: n === "head" ? d.head : limb,
      pinned: false,
    }));
    const bone = (a: Name, b: Name, len: number, stiff = 1): C => ({
      a: I[a],
      b: I[b],
      len,
      stiff,
    });
    const keep = (a: Name, b: Name, len: number): C => ({
      a: I[a],
      b: I[b],
      len,
      min: true,
      stiff: 0.6,
    });
    const arm = d.upper + d.fore;
    const leg = d.thigh + d.shin;
    this.cs = [
      bone("chest", "pelvis", d.torso),
      bone("chest", "head", d.gap + d.head),
      bone("chest", "elbowA", d.upper),
      bone("elbowA", "handA", d.fore),
      bone("chest", "elbowB", d.upper),
      bone("elbowB", "handB", d.fore),
      bone("pelvis", "kneeA", d.thigh),
      bone("kneeA", "footA", d.shin),
      bone("pelvis", "kneeB", d.thigh),
      bone("kneeB", "footB", d.shin),
      // joint limits
      keep("head", "pelvis", d.torso + d.gap + d.head * 0.6),
      keep("pelvis", "footA", leg * 0.42),
      keep("pelvis", "footB", leg * 0.42),
      keep("chest", "handA", arm * 0.35),
      keep("chest", "handB", arm * 0.35),
      keep("kneeA", "kneeB", d.wThigh * 0.8),
      keep("head", "kneeA", d.torso * 0.75),
      keep("head", "kneeB", d.torso * 0.75),
    ];
  }

  /** Start from an animated pose, moving with velocity (vx, vy) px/s plus an optional spin. */
  fromJoints(j: Joints, vx: number, vy: number, spin = 0) {
    const c = j.pelvis;
    const dt = 1 / 60;
    for (const n of NAMES) {
      const q = j[n];
      const p = this.ps[I[n]]!;
      p.x = q.x;
      p.y = q.y;
      // spin: tangential velocity about the pelvis
      const sx = -(q.y - c.y) * spin;
      const sy = (q.x - c.x) * spin;
      p.px = q.x - (vx + sx) * dt;
      p.py = q.y - (vy + sy) * dt;
      p.pinned = false;
    }
    this.pin = null;
  }

  /** Add velocity (px/s) to every particle, or to one. */
  impulse(vx: number, vy: number, only?: number) {
    const dt = 1 / 60;
    this.ps.forEach((p, i) => {
      if (only !== undefined && i !== only) return;
      p.px -= vx * dt;
      p.py -= vy * dt;
    });
  }

  nearest(x: number, y: number) {
    let best = 0;
    let bd = Infinity;
    this.ps.forEach((p, i) => {
      const d = Math.hypot(p.x - x, p.y - y);
      if (d < bd) {
        bd = d;
        best = i;
      }
    });
    return { index: best, dist: bd };
  }

  grab(index: number, at: Vec) {
    this.pin = index;
    this.pinAt = at;
  }

  release(vx: number, vy: number) {
    if (this.pin === null) return;
    const p = this.ps[this.pin]!;
    const dt = 1 / 60;
    p.px = p.x - vx * dt;
    p.py = p.y - vy * dt;
    this.pin = null;
  }

  /** Fastest particle speed, px/s. */
  speed() {
    let m = 0;
    for (const p of this.ps) m = Math.max(m, Math.hypot(p.x - p.px, p.y - p.py) / SUB);
    return m;
  }

  step(dt: number, plats: Plat[], b: Bounds, onImpact?: (i: Impact) => void) {
    let t = Math.min(dt, 0.05);
    const loud: Impact[] = [];
    while (t > 0) {
      const h = Math.min(SUB, t);
      t -= h;
      // integrate
      for (const p of this.ps) {
        const vx = (p.x - p.px) * 0.999;
        const vy = (p.y - p.py) * 0.999;
        p.px = p.x;
        p.py = p.y;
        p.x += vx;
        p.y += vy + GRAVITY * h * h;
      }
      if (this.pin !== null) {
        const p = this.ps[this.pin]!;
        // follow the pointer softly so a fast drag stretches the body a little, then snaps
        p.x += (this.pinAt.x - p.x) * 0.6;
        p.y += (this.pinAt.y - p.y) * 0.6;
      }
      // constraints
      for (let k = 0; k < 6; k++) {
        for (const c of this.cs) {
          const a = this.ps[c.a]!;
          const bb = this.ps[c.b]!;
          const dx = bb.x - a.x;
          const dy = bb.y - a.y;
          const dist = Math.hypot(dx, dy) || 1e-6;
          if (c.min && dist >= c.len) continue;
          const diff = ((dist - c.len) / dist) * 0.5 * c.stiff;
          const wa = this.pin === c.a ? 0 : 1;
          const wb = this.pin === c.b ? 0 : 1;
          const sum = wa + wb || 1;
          a.x += dx * diff * ((2 * wa) / sum);
          a.y += dy * diff * ((2 * wa) / sum);
          bb.x -= dx * diff * ((2 * wb) / sum);
          bb.y -= dy * diff * ((2 * wb) / sum);
        }
      }
      // collisions
      for (const p of this.ps) {
        const vy = (p.y - p.py) / h;
        const vx = (p.x - p.px) / h;
        // one-way platforms: only from above
        for (const pl of plats) {
          if (p.x < pl.left || p.x > pl.right) continue;
          const top = pl.top - p.r;
          if (p.py <= top + 0.5 && p.y > top) {
            p.y = top;
            if (vy > 380) loud.push({ x: p.x, y: pl.top, speed: vy, plat: pl });
            p.py = p.y + vy * h * 0.28; // a little bounce
            p.px = p.x - vx * h * 0.72; // friction
          }
        }
        if (p.y > b.floor - p.r) {
          if (vy > 380) loud.push({ x: p.x, y: b.floor, speed: vy, plat: null });
          p.y = b.floor - p.r;
          p.py = p.y + vy * h * 0.28;
          p.px = p.x - vx * h * 0.72;
        }
        if (p.y < b.ceil + p.r) {
          p.y = b.ceil + p.r;
          p.py = p.y + vy * h * 0.3;
        }
        if (p.x < b.left + p.r || p.x > b.right - p.r) {
          if (Math.abs(vx) > 500) loud.push({ x: p.x, y: p.y, speed: Math.abs(vx), plat: null });
          p.x = Math.max(b.left + p.r, Math.min(b.right - p.r, p.x));
          p.px = p.x + vx * h * 0.35;
        }
      }
    }
    if (onImpact && loud.length) {
      // report the hardest hit per step, not every particle
      loud.sort((a, b) => b.speed - a.speed);
      onImpact(loud[0]!);
    }
  }

  /** Joints for drawing (the shoulder sits a little down the torso, as in the rig). */
  joints(): Joints {
    const g = (n: Name) => ({ x: this.ps[I[n]]!.x, y: this.ps[I[n]]!.y });
    const chest = g("chest");
    const pelvis = g("pelvis");
    const k = this.d.shoulder;
    return {
      head: g("head"),
      chest,
      pelvis,
      shoulder: { x: chest.x + (pelvis.x - chest.x) * k, y: chest.y + (pelvis.y - chest.y) * k },
      elbowA: g("elbowA"),
      handA: g("handA"),
      elbowB: g("elbowB"),
      handB: g("handB"),
      kneeA: g("kneeA"),
      footA: g("footA"),
      kneeB: g("kneeB"),
      footB: g("footB"),
      f: Math.sign(g("head").x - pelvis.x) || 1,
    };
  }
}
