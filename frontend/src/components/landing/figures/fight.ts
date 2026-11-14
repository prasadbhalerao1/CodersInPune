/**
 * Fighting moves for the roaming figure, keyed like the gestures: a chamber (wind-up), a snap
 * to contact, a recovery back to guard. Each strike says when it lands (`hit`) and with which
 * limb, so the controller can aim that limb at the cursor with IK and check for contact.
 */

import { STAND, type Pose } from "./rig";
import { EASE, clip } from "./track";

/** Fighting stance: weight low and staggered, fists up by the chin. */
export const GUARD: Pose = {
  ...STAND,
  lean: 0.12,
  head: 0.05,
  hipA: 0.36,
  kneeA: 0.42,
  hipB: -0.32,
  kneeB: 0.28,
  shA: 1.05,
  elA: 2.25,
  shB: 0.85,
  elB: 2.35,
};

export type Strike = {
  name: string;
  time: number;
  /** When the strike lands (seconds). */
  hit: number;
  /** Which limb lands it. */
  limb: "handA" | "handB" | "footA";
  pose: (t: number) => Pose;
  /** 0..1: how far the striking limb is extended towards the target at `t`. */
  extend: (t: number) => number;
  /** How hard it hits (spark power, knock strength). */
  power: number;
};

const extendCurve = (start: number, hit: number, back: number) => (t: number) =>
  t < start
    ? 0
    : t < hit
      ? EASE.in((t - start) / (hit - start))
      : t < back
        ? 1 - EASE.inOut((t - hit) / (back - hit))
        : 0;

export const JAB: Strike = {
  name: "jab",
  time: 0.34,
  hit: 0.12,
  limb: "handA",
  power: 0.6,
  extend: extendCurve(0.02, 0.12, 0.3),
  pose: clip(
    [
      { t: 0, pose: GUARD, ease: EASE.in },
      { t: 0.12, pose: { ...GUARD, lean: 0.24, head: 0 }, ease: EASE.out },
      { t: 0.34, pose: GUARD },
    ],
    GUARD,
  ),
};

export const CROSS: Strike = {
  name: "cross",
  time: 0.46,
  hit: 0.19,
  limb: "handB",
  power: 1,
  extend: extendCurve(0.06, 0.19, 0.42),
  pose: clip(
    [
      { t: 0, pose: GUARD, ease: EASE.out },
      { t: 0.07, pose: { ...GUARD, lean: 0.02, hipB: -0.42, kneeB: 0.35 }, ease: EASE.snap },
      {
        t: 0.19,
        pose: { ...GUARD, lean: 0.34, head: -0.04, hipA: 0.48, kneeA: 0.5, hipB: -0.5, kneeB: 0.1 },
        ease: EASE.inOut,
      },
      { t: 0.46, pose: GUARD },
    ],
    GUARD,
  ),
};

export const UPPERCUT: Strike = {
  name: "uppercut",
  time: 0.56,
  hit: 0.26,
  limb: "handA",
  power: 1.3,
  extend: extendCurve(0.12, 0.26, 0.5),
  pose: clip(
    [
      { t: 0, pose: GUARD, ease: EASE.in },
      {
        t: 0.12,
        pose: {
          ...GUARD,
          lean: 0.3,
          hipA: 0.7,
          kneeA: 1.05,
          hipB: -0.1,
          kneeB: 0.8,
          shA: 0.3,
          elA: 1.6,
        },
        ease: EASE.snap,
      },
      {
        t: 0.26,
        pose: {
          ...GUARD,
          lean: -0.08,
          head: -0.2,
          hipA: 0.25,
          kneeA: 0.1,
          hipB: -0.25,
          kneeB: 0.1,
        },
        ease: EASE.inOut,
      },
      { t: 0.56, pose: GUARD },
    ],
    GUARD,
  ),
};

/** Kick: chamber the knee, snap the shin out, chamber again, put the foot down. */
export const KICK: Strike = {
  name: "kick",
  time: 0.7,
  hit: 0.32,
  limb: "footA",
  power: 1.4,
  extend: extendCurve(0.18, 0.32, 0.55),
  pose: clip(
    [
      { t: 0, pose: GUARD, ease: EASE.out },
      {
        t: 0.18,
        pose: {
          ...GUARD,
          lean: -0.12,
          hipA: 1.5,
          kneeA: 2.2,
          hipB: -0.05,
          kneeB: 0.15,
          shA: 0.6,
          shB: -0.4,
          elB: 1.2,
        },
        ease: EASE.snap,
      },
      {
        t: 0.32,
        pose: {
          ...GUARD,
          lean: -0.32,
          head: 0.1,
          hipA: 1.55,
          kneeA: 0.05,
          hipB: -0.08,
          kneeB: 0.12,
          shA: 0.3,
          elA: 1.4,
          shB: -0.7,
          elB: 0.9,
        },
        ease: EASE.inOut,
      },
      {
        t: 0.5,
        pose: { ...GUARD, lean: -0.1, hipA: 1.3, kneeA: 2.1, hipB: -0.05, kneeB: 0.15 },
        ease: EASE.inOut,
      },
      { t: 0.7, pose: GUARD },
    ],
    GUARD,
  ),
};

/** "Come on": both hands beckon, chin up. */
export const TAUNT_TIME = 1.5;
const beckonPose = (t: number): Pose => {
  const curl = Math.max(0, Math.sin(t * 11));
  return {
    ...GUARD,
    lean: -0.05,
    head: -0.18,
    shA: 1.35,
    elA: 0.6 + 1.2 * curl,
    shB: 1.25,
    elB: 0.6 + 1.2 * Math.max(0, Math.sin(t * 11 + 0.6)),
    hipA: 0.2,
    kneeA: 0.15,
    hipB: -0.2,
    kneeB: 0.1,
  };
};
export const taunt = (t: number): Pose => beckonPose(t);

/** Shaking a fist at someone, the other hand on the hip. */
export const shakeFist = (t: number): Pose => ({
  ...STAND,
  lean: 0.08,
  head: -0.1,
  shA: 2.3 + 0.12 * Math.sin(t * 24),
  elA: 1.1,
  shB: -0.5,
  elB: 2.4,
});

/** Getting up from the floor: hands down, a knee under, then up. */
export const GETUP_TIME = 0.85;
export const getup = clip([
  {
    t: 0,
    pose: {
      ...STAND,
      lean: 0.9,
      head: 0.4,
      hipA: 1.7,
      kneeA: 2.5,
      hipB: 1.2,
      kneeB: 2.6,
      shA: 0.4,
      elA: 0.1,
      shB: 0.5,
      elB: 0.1,
    },
    ease: EASE.inOut,
  },
  {
    t: 0.35,
    pose: {
      ...STAND,
      lean: 0.55,
      head: 0.25,
      hipA: 1.3,
      kneeA: 2.0,
      hipB: 0.2,
      kneeB: 1.2,
      shA: 0.6,
      elA: 0.4,
      shB: 0.6,
      elB: 0.4,
    },
    ease: EASE.out,
  },
  { t: GETUP_TIME, pose: GUARD },
]);

/** Idle: weight shifts, breathes, glances around. */
export const idle = (t: number): Pose => ({
  ...STAND,
  lean: 0.02 + 0.012 * Math.sin(t * 1.6),
  head: 0.03 * Math.sin(t * 0.7),
  hipA: 0.16 + 0.03 * Math.sin(t * 0.5),
  hipB: -0.2 + 0.03 * Math.sin(t * 0.5),
  shA: 0.3 + 0.03 * Math.sin(t * 1.6),
  shB: -0.26 + 0.03 * Math.sin(t * 1.6 + 0.5),
});

export const STRIKES = { JAB, CROSS, UPPERCUT, KICK };
