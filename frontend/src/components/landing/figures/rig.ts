/**
 * A small 2D skeletal rig for the landing page's figures.
 *
 * What it borrows from the usual ways stick figures are animated:
 * - Keyframed poses, as in hand-animated loops: a pose is a set of joint angles, and gestures
 *   (wave, read, hand over, cheer, sit) are poses blended with easing.
 * - Procedural gait, as in game locomotion: walking and running are functions of a phase that
 *   advances with the distance travelled, so the feet never skate faster than the body moves.
 * - Forward kinematics for the skeleton, plus analytic two-bone inverse kinematics so a hand can
 *   land exactly on a target: the other runner's hand, a ledge, a stack of boxes.
 * - Ground contact: the pelvis height is solved from the legs, so the lowest foot always rests
 *   on the element the figure stands on.
 *
 * Conventions: SVG space (y grows downwards). Limb angles are absolute, measured from straight
 * down, positive towards the direction the figure faces. A knee bends the shin back, an elbow
 * bends the forearm forward. Limb "A" is the near side, "B" the far side.
 */

export type Vec = { x: number; y: number };

export type Pose = {
  lean: number;
  head: number;
  hipA: number;
  kneeA: number;
  hipB: number;
  kneeB: number;
  shA: number;
  elA: number;
  shB: number;
  elB: number;
};

const KEYS = [
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
] as const satisfies readonly (keyof Pose)[];

export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
export const clamp01 = (t: number) => Math.min(1, Math.max(0, t));
export const smooth = (t: number) => {
  const x = clamp01(t);
  return x * x * (3 - 2 * x);
};
/** Frame-rate independent exponential approach: the share of the gap to close this frame. */
export const approach = (dt: number, rate: number) => 1 - Math.exp(-dt * rate);
export const vlerp = (a: Vec, b: Vec, t: number): Vec => ({
  x: lerp(a.x, b.x, t),
  y: lerp(a.y, b.y, t),
});

export function mix(a: Pose, b: Pose, t: number): Pose {
  const out = { ...a };
  for (const k of KEYS) out[k] = lerp(a[k], b[k], t);
  return out;
}

// ── Poses ────────────────────────────────────────────────────────────────────────────────

export const STAND: Pose = {
  // a side view of someone standing is nearly a line, so the rest pose keeps a little spread:
  // weight on the near leg, the far leg a step back, the arms just clear of the body
  lean: 0.02,
  head: 0,
  hipA: 0.16,
  kneeA: 0.1,
  hipB: -0.2,
  kneeB: 0.06,
  shA: 0.34,
  elA: 0.3,
  shB: -0.3,
  elB: 0.22,
};

const pose = (p: Partial<Pose>): Pose => ({ ...STAND, ...p });

/** Receiver in the exchange zone: crouched, leaning, far hand reaching back for the baton. */
export const READY = pose({
  lean: 0.42,
  head: -0.3,
  hipA: 0.55,
  kneeA: 0.95,
  hipB: -0.25,
  kneeB: 0.5,
  shA: 0.5,
  elA: 1.2,
  shB: -1.05,
  elB: 0.12,
});

/** Arms forward, forearms level: ready to take the load. */
export const CARRY = pose({ lean: -0.05, head: 0.12, shA: 0.72, elA: 0.92, shB: 0.62, elB: 1.0 });

/** Carrying more than one person should: knees give, the back rounds. */
export const STRAIN = pose({
  lean: 0.14,
  head: 0.22,
  hipA: 0.32,
  kneeA: 0.62,
  hipB: 0.12,
  kneeB: 0.5,
  shA: 0.6,
  elA: 1.02,
  shB: 0.52,
  elB: 1.08,
});

/** Hand to chin, looking down at the work. */
export const THINK = pose({ head: 0.26, shA: 0.28, elA: 2.55, shB: 0.4, elB: 1.25 });

/** Reading a document held at chest height. */
export const READ = pose({ lean: 0.05, head: 0.4, shA: 0.55, elA: 1.25, shB: 0.45, elB: 1.32 });

/** Holding a document out to someone. */
export const PRESENT = pose({ lean: 0.06, head: 0.08, shA: 1.2, elA: 0.28, shB: 0.1, elB: 0.2 });

/** Baton held up. */
export const CHEER = pose({ lean: -0.04, head: -0.22, shA: 2.95, elA: 0.12, shB: -0.12, elB: 0.3 });

/** Sitting on a ledge with the legs over the edge, swinging out of step. */
export const sit = (t: number): Pose =>
  pose({
    lean: -0.12,
    head: 0.05 + 0.1 * Math.sin(t * 0.7),
    hipA: 1.5,
    kneeA: 1.45 + 0.28 * Math.sin(t * 2.4),
    hipB: 1.42,
    kneeB: 1.45 + 0.28 * Math.sin(t * 2.4 + 1.9),
  });

// ── Locomotion ───────────────────────────────────────────────────────────────────────────

/** A walk (run = 0) through a run (run = 1) at the given phase (radians). */
export function gait(phase: number, run: number): Pose {
  const s = Math.sin(phase);
  const hip = lerp(0.4, 0.8, run);
  const kneeBase = lerp(0.08, 0.32, run);
  const kneeSwing = lerp(0.75, 1.75, run);
  const arm = lerp(0.34, 0.95, run);
  const elbow = lerp(0.28, 1.45, run);
  // the knee folds while its leg swings forward, peaking just after it passes under the body
  const knee = (ph: number) => kneeBase + kneeSwing * Math.max(0, Math.cos(ph - 0.35)) ** 1.3;
  // overlapping action: the forearm trails its upper arm by a fraction of a step, the trunk
  // pitches a touch on each footfall and the head counters it, so nothing moves in lockstep
  const lag = 0.55;
  const fall = Math.cos(2 * phase);
  return {
    lean: lerp(0.04, 0.26, run) + lerp(0.015, 0.035, run) * fall,
    head: lerp(0, -0.14, run) - lerp(0.03, 0.05, run) * fall,
    hipA: hip * s,
    kneeA: knee(phase),
    hipB: -hip * s,
    kneeB: knee(phase + Math.PI),
    shA: -arm * s * 0.9,
    elA: elbow + lerp(0.2, 0.35, run) * Math.max(0, -Math.sin(phase - lag)),
    shB: arm * s * 0.9,
    elB: elbow + lerp(0.2, 0.35, run) * Math.max(0, Math.sin(phase - lag)),
  };
}

/** Distance covered by one full gait cycle (two steps). */
export const stride = (run: number, H: number) => lerp(0.9, 1.95, run) * H;

/** Running has a flight phase between steps: lift the body while the legs are spread. */
export const runLift = (phase: number, run: number, H: number) =>
  (run * 0.05 * H * (1 - Math.cos(2 * phase))) / 2;

// ── Skeleton ─────────────────────────────────────────────────────────────────────────────

export type Dims = ReturnType<typeof dims>;

/**
 * Proportions for a figure `H` pixels tall (sole to crown), in the studio stick-figure style:
 * one heavy, even line weight (about 7% of the height) with round ends, a large solid head
 * (about a fifth of the height) sitting just above a long torso, shoulders set a little below
 * the neck, and no feet. The weight is what makes a line figure read as a body rather than
 * as a sketch.
 */
export function dims(H: number) {
  const w = (share: number) => Math.max(2, share * H);
  return {
    H,
    head: 0.1 * H,
    gap: 0.014 * H,
    torso: 0.355 * H,
    /** How far below the top of the torso the arms attach (share of the torso). */
    shoulder: 0.14,
    thigh: 0.225 * H,
    shin: 0.222 * H,
    upper: 0.175 * H,
    fore: 0.165 * H,
    foot: 0,
    /** Per-segment line weights: nearly even, a touch heavier through the trunk and thighs. */
    wTorso: w(0.078),
    wThigh: w(0.074),
    wShin: w(0.07),
    wUpper: w(0.068),
    wFore: w(0.066),
    wHead: 0,
    /** The base weight props (batons, boxes, ropes) are drawn at. */
    stroke: w(0.05),
  };
}

export type Joints = {
  pelvis: Vec;
  chest: Vec;
  /** Where the arms attach: a little below the top of the torso. */
  shoulder: Vec;
  head: Vec;
  kneeA: Vec;
  footA: Vec;
  kneeB: Vec;
  footB: Vec;
  elbowA: Vec;
  handA: Vec;
  elbowB: Vec;
  handB: Vec;
  /** The facing the joints were solved with (1 right, -1 left, 0 towards the viewer). */
  f: number;
};

const limb = (o: Vec, angle: number, len: number, f: number): Vec => ({
  x: o.x + f * Math.sin(angle) * len,
  y: o.y + Math.cos(angle) * len,
});

/** How far below the pelvis the lower foot sits. */
export function legDrop(p: Pose, d: Dims) {
  const a = d.thigh * Math.cos(p.hipA) + d.shin * Math.cos(p.hipA - p.kneeA);
  const b = d.thigh * Math.cos(p.hipB) + d.shin * Math.cos(p.hipB - p.kneeB);
  return Math.max(a, b);
}

/**
 * Analytic two-bone IK: the joint between two bones (lengths l1, l2) from `a` such that the
 * end lands on `t`, or as close as the bones reach. `bend` (±1) picks which side the joint
 * folds to. Returns [middle joint, end].
 */
export function ik(a: Vec, t: Vec, l1: number, l2: number, bend: number): [Vec, Vec] {
  const dx = t.x - a.x;
  const dy = t.y - a.y;
  const raw = Math.hypot(dx, dy) || 1e-6;
  const dist = Math.min(l1 + l2 - 1e-3, Math.max(Math.abs(l1 - l2) + 1e-3, raw));
  const cos = (l1 * l1 + dist * dist - l2 * l2) / (2 * l1 * dist);
  const ang = Math.atan2(dy, dx) + bend * Math.acos(Math.max(-1, Math.min(1, cos)));
  const mid = { x: a.x + Math.cos(ang) * l1, y: a.y + Math.sin(ang) * l1 };
  const end = { x: a.x + (dx / raw) * dist, y: a.y + (dy / raw) * dist };
  return [mid, end];
}

export type Reach = {
  /** Where the hand should go; blended in by `w` (0 = pose, 1 = exactly on target). */
  target: Vec;
  w?: number;
  /** +1 folds the elbow below the shoulder-to-hand line for a figure facing right. */
  bend?: number;
};

export type SolveOptions = {
  /** Extra height above the ground (a run's flight phase, a jump). */
  lift?: number;
  /** Pin the pelvis instead of standing on the ground (sitting). */
  pelvisY?: number;
  /** Shift the head: looking at something (a cursor) without turning the body. */
  gaze?: Vec;
  reachA?: Reach;
  reachB?: Reach;
};

/**
 * Joint positions for a pose. `x` is the pelvis, `groundY` what the feet rest on, `f` the facing
 * (1 right, -1 left; values in between read as the figure turning).
 */
export function solve(
  p: Pose,
  d: Dims,
  x: number,
  groundY: number,
  f: number,
  o: SolveOptions = {},
): Joints {
  const pelvis = { x, y: o.pelvisY ?? groundY - legDrop(p, d) - (o.lift ?? 0) };
  const chest = {
    x: pelvis.x + f * Math.sin(p.lean) * d.torso,
    y: pelvis.y - Math.cos(p.lean) * d.torso,
  };
  const tilt = p.lean + p.head;
  const r = d.gap + d.head;
  const head = {
    x: chest.x + f * Math.sin(tilt) * r + (o.gaze?.x ?? 0),
    y: chest.y - Math.cos(tilt) * r + (o.gaze?.y ?? 0),
  };
  // Facing 0 is the front view: the near limbs open to one side and the far limbs to the other,
  // so a figure that turns to the viewer does not collapse into a line. Continuous in f.
  const spread = 1 - Math.abs(f);
  const fA = f + spread;
  const fB = f - spread;
  // Seen from the front, limbs open outwards: blend each angle towards its magnitude plus a
  // little spread as the figure turns to the viewer. In side view (|f| = 1) this is a no-op.
  const front = 1 - Math.abs(f);
  const open = (angle: number, extra: number) => lerp(angle, Math.abs(angle) + extra, front);
  const hipA = open(p.hipA, 0.1);
  const hipB = open(p.hipB, 0.1);
  const kneeA = limb(pelvis, hipA, d.thigh, fA);
  const kneeB = limb(pelvis, hipB, d.thigh, fB);
  const footA = limb(kneeA, hipA - p.kneeA, d.shin, fA);
  const footB = limb(kneeB, hipB - p.kneeB, d.shin, fB);

  const shoulder = vlerp(chest, pelvis, d.shoulder);
  const arm = (sh: number, el: number, fl: number, reach?: Reach): [Vec, Vec] => {
    const elbow = limb(shoulder, sh, d.upper, fl);
    const hand = limb(elbow, sh + el, d.fore, fl);
    if (!reach || (reach.w ?? 1) <= 0) return [elbow, hand];
    const goal = vlerp(hand, reach.target, clamp01(reach.w ?? 1));
    return ik(shoulder, goal, d.upper, d.fore, (reach.bend ?? 1) * (fl < 0 ? -1 : 1));
  };
  const [elbowA, handA] = arm(open(p.shA, 0.1), p.elA, fA, o.reachA);
  const [elbowB, handB] = arm(open(p.shB, 0.1), p.elB, fB, o.reachB);
  return {
    pelvis,
    chest,
    shoulder,
    head,
    kneeA,
    footA,
    kneeB,
    footB,
    elbowA,
    handA,
    elbowB,
    handB,
    f,
  };
}
