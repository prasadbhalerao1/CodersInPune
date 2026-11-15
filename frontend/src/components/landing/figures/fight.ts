/**
 * Getting up off the floor after a fall, keyed: hands down, a knee under, then up into a ready
 * stance. Used by the films whenever a figure has ended up as a ragdoll.
 */

import { STAND, type Pose } from "./rig";
import { EASE, clip } from "./track";

/** A ready stance: weight low and staggered, hands up. */
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
