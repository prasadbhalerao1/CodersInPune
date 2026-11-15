/**
 * The balloon: a figure strolls in, takes a balloon from his pocket and blows it up in four
 * breaths. Once it is big enough it lifts him off his feet; he dangles below it, swaying like a
 * pendulum as a breeze carries him up towards a heading, until the balloon meets the point of
 * a letter and pops. He falls (a ragdoll; whatever he lands on shakes), gets up, dusts himself
 * off, shrugs at the reader and walks away.
 */

import { getup, GETUP_TIME } from "../fight";
import { knock } from "../physics";
import { Ragdoll } from "../ragdoll";
import {
  Actor,
  FRONT,
  Fx,
  SHRUG,
  cardTops,
  findChars,
  hang,
  reach,
  type Ink,
  type Joints,
  type Vec,
} from "../filmkit";
import type { Running, Script } from "../film-layer";
import { STAND, smooth, solve } from "../rig";

const POINTY = "iAtlkjfT!";

function target(H: number) {
  const floor = window.scrollY + window.innerHeight - 10;
  const c = findChars(POINTY, 4.6 * H, floor);
  c.sort(
    (p, q) =>
      Math.abs(p.rect.left - window.innerWidth / 2) - Math.abs(q.rect.left - window.innerWidth / 2),
  );
  return c[0] ?? null;
}

const sizeH = () => (window.innerWidth < 640 ? 70 : 96);

export const balloon: Script = {
  name: "balloon",
  idleAfter: 9,
  ready: () => !!target(sizeH()),
  start: (): Running => {
    const H = sizeH();
    const tg = target(H)!;
    const sy = window.scrollY;
    const tip: Vec = {
      x: tg.rect.left + tg.rect.width / 2,
      y: tg.rect.bottom + sy - tg.rect.height * 0.12,
    };
    const heading = (tg.node.parentElement?.closest("h1, h2") as HTMLElement | null) ?? null;
    const floor = sy + window.innerHeight - 10;
    const side = tip.x > window.innerWidth / 2 ? 1 : -1;
    const a = new Actor(H, side > 0 ? window.innerWidth + H : -H, floor, -side);
    const fx = new Fx();
    let st = "walk";
    let t = 0;
    const go = (s: string) => {
      st = s;
      t = 0;
    };
    // the balloon
    let r = 0;
    let bx = 0;
    let by = 0;
    let bvx = 0;
    let bvy = 0;
    let sway = 0;
    let swayV = 0;
    let lastAx = 0;
    const string = 0.95 * H;
    let rag: Ragdoll | null = null;
    let from: Joints | null = null;
    let quiet = 0;
    let groundY = floor;
    let popped = false;

    const step = (dt: number) => {
      t += dt;
      fx.step(dt);
      let shot: Parameters<Actor["pose2joints"]>[1] = {};
      switch (st) {
        case "walk":
          if (a.walkTo(tip.x + side * 0.9 * H, 1.25 * H, dt)) go("pocket");
          break;
        case "pocket": {
          a.turnTo(-side, dt);
          a.settle({ ...STAND, head: 0.25 }, dt);
          const k = t / 0.6;
          shot = {
            reachA: reach(
              k < 0.5
                ? { x: a.x + a.f * 0.1 * H, y: a.y - 0.42 * H }
                : { x: a.x + a.f * 0.32 * H, y: a.y - 0.85 * H },
              smooth(k * 3),
            ),
          };
          if (k > 0.5) r = 0.06 * H;
          if (k >= 1) go("blow");
          break;
        }
        case "blow": {
          // four breaths: lean back to inhale, lean in to blow; it grows on each blow
          a.turnTo(-side, dt);
          const breath = t % 0.85;
          const blowing = breath > 0.4;
          a.settle(
            {
              ...STAND,
              lean: blowing ? 0.12 : -0.08,
              head: blowing ? 0.05 : -0.15,
              shA: 0.9,
              elA: 1.4,
            },
            dt,
            10,
          );
          if (blowing) r += dt * 0.42 * H * 0.95;
          const j = a.j;
          const mouth = j
            ? { x: j.head.x + a.f * 0.12 * H, y: j.head.y + 0.03 * H }
            : { x: a.x, y: a.y - H };
          shot = { reachA: reach({ x: mouth.x + a.f * r * 0.2, y: mouth.y + 0.04 * H }) };
          bx = mouth.x + a.f * (r + 0.02 * H);
          by = mouth.y;
          if (t > 0.85 * 4) {
            r = 0.42 * H;
            go("tie");
          }
          break;
        }
        case "tie": {
          // tie it off; it rises to the end of its string
          a.settle({ ...STAND, head: -0.2 }, dt);
          const hand = { x: a.x + a.f * 0.3 * H, y: a.y - 0.95 * H };
          shot = { reachA: reach(hand) };
          bx += (hand.x - bx) * Math.min(1, dt * 6);
          by += (hand.y - string - r - by) * Math.min(1, dt * 6);
          if (t > 0.9) go("lift");
          break;
        }
        case "lift": {
          // buoyancy beats his weight; a breeze steers towards the letter
          const up = -1.0 * H;
          bvy += (up - bvy) * Math.min(1, dt * 1.2);
          const ax = 2.2 * (tip.x - bx) - 1.8 * bvx + Math.sin(t * 1.3) * 0.4 * H;
          bvx += ax * dt;
          bx += bvx * dt;
          by += bvy * dt;
          // the body is a pendulum under the hand: it lags behind accelerations
          const L = string * 0.6 + H * 0.7;
          const swayAcc = (-2600 / L) * Math.sin(sway) - ((ax - lastAx) * 0 + ax) / L - 2.2 * swayV;
          lastAx = ax;
          swayV += swayAcc * dt;
          sway += swayV * dt;
          const hand = { x: bx, y: by + r + string };
          a.f = -side;
          const pelvisY = hang(a, hand, sway, {
            hipA: 0.25 + 0.15 * Math.sin(t * 3),
            kneeA: 0.4 + 0.3 * Math.max(0, Math.sin(t * 3)),
            hipB: 0.05 - 0.15 * Math.sin(t * 3),
            kneeB: 0.3,
          });
          shot = {
            pelvisY,
            reachA: reach(hand),
            reachB: reach({ x: hand.x, y: hand.y + 0.06 * H }),
          };
          groundY = floor;
          // the balloon meets the point of the letter
          if (by - r <= tip.y && Math.abs(bx - tip.x) < r) {
            popped = true;
            fx.bits(bx, by - r * 0.3, 16, 1);
            fx.ring(bx, by, r * 1.4);
            fx.sparks(tip.x, tip.y, 0.5, Math.PI / 2, 1.8);
            knock(heading, { y: -120, r: 0.6 }, 1.2);
            const j0 = a.pose2joints(dt, shot);
            rag = new Ragdoll(a.d);
            rag.fromJoints(j0, bvx * 0.6, 120, side * 1.5);
            go("fall");
            return false;
          }
          if (by < sy - 2 * H || t > 12) return true;
          break;
        }
        case "fall": {
          const plats = cardTops(window.scrollY + 80, floor).map((c) => ({
            el: c.el,
            left: c.left,
            right: c.right,
            top: c.y,
          }));
          rag!.step(
            dt,
            plats,
            { left: 4, right: window.innerWidth - 4, ceil: window.scrollY + 70, floor },
            (hit) => {
              fx.dust(hit.x, hit.y, Math.min(1.5, hit.speed / 1200));
              if (hit.plat?.el)
                knock(hit.plat.el, { y: Math.min(420, hit.speed * 0.25), r: side * 1.5 }, 0.9);
              groundY = hit.y;
            },
          );
          const j = rag!.joints();
          quiet = rag!.speed() < 70 ? quiet + dt : 0;
          if (quiet > 0.6) {
            from = j;
            a.x = j.pelvis.x;
            a.y = groundY;
            a.f = side;
            go("getup");
          }
          a.j = j;
          return false;
        }
        case "getup": {
          const target2 = solve(getup(t), a.d, a.x, a.y, a.f);
          a.j = from ? blendJ(from, target2, smooth(t / 0.45)) : target2;
          a.pose = getup(t);
          if (t >= GETUP_TIME) go("dust");
          return false;
        }
        case "dust": {
          // pat the dust off: hands to thighs and chest in turn
          a.settle({ ...STAND, lean: 0.25, head: 0.35 }, dt);
          const j = a.j;
          if (j) {
            const beat = Math.floor(t * 6) % 2;
            shot = {
              reachA: reach(
                beat
                  ? { x: j.pelvis.x + a.f * 0.08 * H, y: j.pelvis.y + 0.12 * H }
                  : { x: j.chest.x + a.f * 0.1 * H, y: j.chest.y + 0.1 * H },
              ),
              reachB: reach(
                beat
                  ? { x: j.chest.x + a.f * 0.06 * H, y: j.chest.y + 0.15 * H }
                  : { x: j.pelvis.x + a.f * 0.1 * H, y: j.pelvis.y + 0.1 * H },
              ),
            };
            if (Math.floor((t - dt) * 6) !== Math.floor(t * 6))
              fx.dust(j.pelvis.x, j.pelvis.y, 0.15);
          }
          if (t > 1.3) go("shrug");
          break;
        }
        case "shrug":
          a.turnTo(0, dt);
          a.settle(t < 1.1 ? SHRUG : FRONT, dt, 8);
          if (t > 1.6) go("leave");
          break;
        case "leave": {
          const out = a.x > window.innerWidth / 2 ? window.innerWidth + 1.2 * H : -1.2 * H;
          if (a.walkTo(out, 1.3 * H, dt)) return true;
          break;
        }
      }
      if (st !== "fall" && st !== "getup") a.pose2joints(dt, shot);
      return false;
    };

    return {
      step,
      draw: (ctx: CanvasRenderingContext2D, ink: Ink) => {
        const ground = st === "lift" ? floor : a.y;
        a.draw(ctx, ink, st === "fall" ? undefined : ground);
        if (!popped && r > 0) {
          const hand = a.j ? a.j.handA : { x: bx, y: by + r };
          const knot = { x: bx, y: by + r };
          // string
          if (st !== "blow" && st !== "pocket") {
            ctx.strokeStyle = ink.ink;
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            ctx.moveTo(knot.x, knot.y);
            ctx.quadraticCurveTo(
              (knot.x + hand.x) / 2 + Math.sin(t * 4) * 6,
              (knot.y + hand.y) / 2,
              hand.x,
              hand.y,
            );
            ctx.stroke();
          }
          // the balloon: slightly taller than wide, a highlight, a knot
          ctx.fillStyle = ink.accent;
          ctx.globalAlpha = 0.92;
          ctx.beginPath();
          ctx.ellipse(bx, by, r * 0.88, r, 0, 0, Math.PI * 2);
          ctx.fill();
          ctx.globalAlpha = 0.35;
          ctx.fillStyle = "#ffffff";
          ctx.beginPath();
          ctx.ellipse(bx - r * 0.3, by - r * 0.35, r * 0.18, r * 0.28, -0.5, 0, Math.PI * 2);
          ctx.fill();
          ctx.globalAlpha = 1;
          ctx.fillStyle = ink.accent;
          ctx.beginPath();
          ctx.moveTo(knot.x - 4, knot.y + 5);
          ctx.lineTo(knot.x + 4, knot.y + 5);
          ctx.lineTo(knot.x, knot.y - 1);
          ctx.fill();
        }
        fx.draw(ctx, ink);
      },
      cleanup: () => {},
    };
  },
};

function blendJ(a: Joints, b: Joints, k: number): Joints {
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
