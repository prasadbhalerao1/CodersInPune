/**
 * Hand-keyed gestures. Each one has the beats an animator would give it: an anticipation
 * (a small move the opposite way), the action on a snap, then a settle. Times are in seconds.
 */

import { STAND, type Pose } from "./rig";
import { EASE, bezier, clip, type Ease } from "./track";

const rest: Partial<Pose> = { shA: 0.3, elA: 0.3 };

/** Raise the near arm (with a dip first), then wave from the elbow, looping while it lasts. */
const waveIn = clip([
  { t: 0, pose: rest, ease: EASE.in },
  { t: 0.16, pose: { shA: 0.05, elA: 0.7, lean: 0.04, head: 0.06 }, ease: EASE.snap },
  { t: 0.42, pose: { shA: 2.72, elA: 0.25, lean: -0.03, head: -0.08 } },
]);
const waveLoop = clip(
  [
    { t: 0, pose: { shA: 2.72, elA: 0.25, lean: -0.03, head: -0.08 }, ease: EASE.inOut },
    { t: 0.17, pose: { shA: 2.62, elA: 0.95, lean: -0.03, head: -0.06 }, ease: EASE.inOut },
    { t: 0.34, pose: { shA: 2.72, elA: 0.25, lean: -0.03, head: -0.08 } },
  ],
  STAND,
  true,
);
export const wave = (t: number): Pose => (t < 0.42 ? waveIn(t) : waveLoop(t - 0.42));

/** A nod with a pause between: down fast, back up on a slight overshoot. */
export const nod = clip(
  [
    { t: 0, pose: { head: 0.04 }, ease: EASE.in },
    { t: 0.16, pose: { head: 0.36, lean: 0.03 }, ease: EASE.snap },
    { t: 0.42, pose: { head: 0.02 }, ease: EASE.hold },
    { t: 1.0, pose: { head: 0.04 } },
  ],
  STAND,
  true,
);

/**
 * A shove, facing the viewer with the near arm: wind back, drive through on a snap, hold the
 * push, recover. `push` (0..1) is how far the target is being pushed at that moment.
 */
export const SHOVE_TIME = 1.0;
const shovePose = clip([
  { t: 0, pose: { shA: 1.0, elA: 1.2, lean: 0 }, ease: EASE.out },
  {
    t: 0.28,
    pose: { shA: 0.75, elA: 2.0, lean: -0.18, head: -0.06, hipA: 0.28, kneeA: 0.35 },
    ease: EASE.snap,
  },
  {
    t: 0.46,
    pose: { shA: 1.6, elA: 0.08, lean: 0.32, head: 0.1, hipB: -0.45, kneeB: 0.15 },
    ease: EASE.hold,
  },
  {
    t: 0.7,
    pose: { shA: 1.6, elA: 0.08, lean: 0.32, head: 0.1, hipB: -0.45, kneeB: 0.15 },
    ease: EASE.inOut,
  },
  { t: SHOVE_TIME, pose: { shA: 0.35, elA: 0.35, lean: 0.02 } },
]);
const pushCurve = bezier(0.2, 0.9, 0.3, 1);
export const shove = (t: number) => ({
  pose: shovePose(t),
  push:
    t < 0.34
      ? 0
      : t < 0.5
        ? pushCurve((t - 0.34) / 0.16)
        : t < 0.72
          ? 1
          : 1 - EASE.inOut((t - 0.72) / 0.28),
});

/** Three raps on the glass, the forearm snapping in each time, then a step back. */
export const KNOCK_TIME = 2.0;
const rap = (t: number, ease: Ease = EASE.snap) => ({
  t,
  pose: { shA: 1.7, elA: 0.55, lean: 0.12, head: -0.04 },
  ease,
});
const back = (t: number) => ({
  t,
  pose: { shA: 1.75, elA: 1.55, lean: 0.06, head: -0.04 },
  ease: EASE.in,
});
export const knock = clip([
  { t: 0, pose: { shA: 0.4, elA: 0.4 }, ease: EASE.inOut },
  back(0.35),
  rap(0.47),
  back(0.62),
  rap(0.74),
  back(0.89),
  rap(1.01),
  { t: 1.3, pose: { shA: 1.75, elA: 1.4, lean: 0.02, head: 0.1 }, ease: EASE.inOut },
  { t: KNOCK_TIME, pose: { shA: 0.3, elA: 0.3, lean: 0 } },
]);

/** "Down here": the arm sweeps from raised to pointing down, twice. */
export const BECKON_TIME = 1.8;
const up = (t: number) => ({ t, pose: { shA: 2.5, elA: 0.4, head: -0.05 }, ease: EASE.inOut });
const down = (t: number) => ({
  t,
  pose: { shA: 0.75, elA: 0.6, head: 0.25, lean: 0.06 },
  ease: EASE.inOut,
});
export const beckon = clip([
  { t: 0, pose: rest, ease: EASE.out },
  up(0.3),
  down(0.65),
  up(1.0),
  down(1.35),
  { t: BECKON_TIME, pose: rest },
]);

/** Arms up, a little hop on each beat. `lift` is the hop height as a share of H. */
export const cheer = (t: number) => {
  const beat = (t % 0.42) / 0.42;
  const hop = Math.sin(Math.PI * EASE.out(beat));
  return {
    pose: {
      ...STAND,
      lean: -0.04,
      head: -0.2,
      shA: 2.95 + 0.12 * Math.sin(t * 12),
      elA: 0.12,
      shB: 2.85 - 0.12 * Math.sin(t * 12),
      elB: 0.15,
      hipA: 0.2 + 0.25 * (1 - hop),
      kneeA: 0.2 + 0.5 * (1 - hop),
      hipB: 0.1 + 0.25 * (1 - hop),
      kneeB: 0.2 + 0.5 * (1 - hop),
    },
    lift: hop * 0.12,
  };
};

/**
 * One haul on a rope, as a cycle (0..1): reach forward along the rope, grip, drive back with the
 * legs and lean, then recover. `draw` (0..1) is how much rope has come in during the cycle.
 */
const haulPose = clip(
  [
    {
      t: 0,
      pose: { lean: -0.12, head: 0.2, hipA: 0.35, kneeA: 0.55, hipB: -0.3, kneeB: 0.25 },
      ease: EASE.in,
    },
    {
      t: 0.3,
      pose: { lean: -0.12, head: 0.2, hipA: 0.35, kneeA: 0.55, hipB: -0.3, kneeB: 0.25 },
      ease: EASE.snap,
    },
    {
      t: 0.62,
      pose: { lean: -0.55, head: 0.42, hipA: 0.7, kneeA: 0.22, hipB: -0.55, kneeB: 0.1 },
      ease: EASE.out,
    },
    { t: 1, pose: { lean: -0.12, head: 0.2, hipA: 0.35, kneeA: 0.55, hipB: -0.3, kneeB: 0.25 } },
  ],
  STAND,
  true,
);
export const haul = (cycle: number) => {
  const c = ((cycle % 1) + 1) % 1;
  const draw = c < 0.3 ? 0 : c < 0.62 ? EASE.out((c - 0.3) / 0.32) : 1;
  return { pose: haulPose(c), draw, reach: c < 0.3 ? 1 - EASE.inOut(c / 0.3) * 0.15 : 1 };
};

/** Three stamps with the near foot, knee driving up each time. */
export const STOMP_TIME = 1.4;
const lift = (t: number) => ({
  t,
  pose: { hipA: 1.15, kneeA: 1.7, lean: 0.05, head: 0.15 },
  ease: EASE.in,
});
const stamp = (t: number) => ({
  t,
  pose: { hipA: 0.12, kneeA: 0.08, lean: 0.12, head: 0.22 },
  ease: EASE.out,
});
export const stomp = clip([
  { t: 0, pose: { hipA: 0.15, kneeA: 0.1 }, ease: EASE.out },
  lift(0.18),
  stamp(0.34),
  lift(0.56),
  stamp(0.72),
  lift(0.94),
  stamp(1.1),
  { t: STOMP_TIME, pose: { hipA: 0.15, kneeA: 0.1, lean: 0.02 } },
]);
/** Whether a stamp is landing at `t` (the target dips). */
export const stamping = (t: number) => [0.34, 0.72, 1.1].some((s) => t >= s && t < s + 0.08);
