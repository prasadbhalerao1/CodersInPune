/**
 * Keyframed motion for the figures: a gesture is a list of poses at times, each carrying the
 * easing of its transition into the next. This is how hand-animated stick-figure loops are
 * made, and it is what gives a move anticipation, a snap and a settle instead of the even
 * swing of a sine wave.
 *
 * Timing curves are the standard cubic-bezier ones (ease in (0.42,0,1,1), ease out
 * (0,0,0.58,1), ease in-out (0.42,0,0.58,1)) plus an overshoot for snaps. Angles interpolate
 * along the shortest arc, so a joint never spins the long way round between two keys.
 */

import { STAND, type Pose } from "./rig";

export type Ease = (x: number) => number;

/** A CSS-style cubic-bezier timing function (x1, x2 in [0,1]). */
export function bezier(x1: number, y1: number, x2: number, y2: number): Ease {
  const cx = 3 * x1;
  const bx = 3 * (x2 - x1) - cx;
  const ax = 1 - cx - bx;
  const cy = 3 * y1;
  const by = 3 * (y2 - y1) - cy;
  const ay = 1 - cy - by;
  const sx = (u: number) => ((ax * u + bx) * u + cx) * u;
  const sy = (u: number) => ((ay * u + by) * u + cy) * u;
  const dx = (u: number) => (3 * ax * u + 2 * bx) * u + cx;
  return (x: number) => {
    if (x <= 0) return 0;
    if (x >= 1) return 1;
    // Newton, then bisection if the slope is too flat to trust
    let u = x;
    for (let i = 0; i < 6; i++) {
      const err = sx(u) - x;
      const d = dx(u);
      if (Math.abs(err) < 1e-5) return sy(u);
      if (Math.abs(d) < 1e-6) break;
      u -= err / d;
    }
    let lo = 0;
    let hi = 1;
    u = x;
    for (let i = 0; i < 24; i++) {
      const v = sx(u);
      if (Math.abs(v - x) < 1e-5) break;
      if (v < x) lo = u;
      else hi = u;
      u = (lo + hi) / 2;
    }
    return sy(u);
  };
}

export const EASE = {
  linear: ((x: number) => x) as Ease,
  in: bezier(0.42, 0, 1, 1),
  out: bezier(0, 0, 0.58, 1),
  inOut: bezier(0.42, 0, 0.58, 1),
  /** Arrives early and settles back: a snap. */
  snap: bezier(0.34, 1.45, 0.64, 1),
  /** Holds the outgoing pose until the next key. */
  hold: ((x: number) => (x < 1 ? 0 : 1)) as Ease,
};

export type Key = {
  /** Seconds from the start of the clip. */
  t: number;
  pose: Partial<Pose>;
  /** Easing of the transition from this key to the next (default in-out). */
  ease?: Ease;
};

const ANGLES = new Set<keyof Pose>([
  "lean",
  "head",
  "hipA",
  "kneeA",
  "hipB",
  "kneeB",
  "shA",
  "elA",
  "shB",
  "elB",
]);

/** a → b along the shortest arc. */
function lerpAngle(a: number, b: number, k: number) {
  let d = b - a;
  while (d > Math.PI) d -= 2 * Math.PI;
  while (d < -Math.PI) d += 2 * Math.PI;
  return a + d * k;
}

/**
 * A clip: the pose at time `t` (seconds). Keys fill unspecified joints from `base`. Past the
 * last key the clip holds, or wraps when `loop` is set (the last key then eases into the first).
 */
export function clip(keys: Key[], base: Pose = STAND, loop = false) {
  const full = keys.map((k) => ({ ...k, pose: { ...base, ...k.pose } as Pose }));
  const end = full[full.length - 1]!.t;
  return (t: number): Pose => {
    if (full.length === 1) return full[0]!.pose;
    let time = t;
    if (loop && end > 0) time = ((t % end) + end) % end;
    if (time <= full[0]!.t) return full[0]!.pose;
    if (time >= end) return full[full.length - 1]!.pose;
    let i = 0;
    while (i < full.length - 2 && time >= full[i + 1]!.t) i++;
    const a = full[i]!;
    const b = full[i + 1]!;
    const span = b.t - a.t;
    const k = (a.ease ?? EASE.inOut)(span > 0 ? (time - a.t) / span : 1);
    const out = { ...a.pose };
    for (const key of ANGLES) out[key] = lerpAngle(a.pose[key], b.pose[key], k);
    return out;
  };
}

/** The length of a clip in seconds. */
export const duration = (keys: Key[]) => keys[keys.length - 1]!.t;
