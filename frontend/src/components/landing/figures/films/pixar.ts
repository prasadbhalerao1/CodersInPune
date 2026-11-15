/**
 * The logo film, after the classic animated-studio ident: when the reader reaches the RELAY
 * wordmark and stops, a figure hops in like a desk lamp, sizes up the Y, climbs onto it and
 * bounces until the Y squashes flat. A guilty look at the reader, a shrug, then he uses the
 * flattened Y as a trampoline: it springs back up and throws him into a backflip that lands
 * him on the point of the A. He balances, bows, and the letters ripple like applause before he
 * hops off. The letters are the real ones on the page, squashing and stretching on springs.
 */

import { Spring, knock } from "../physics";
import { Actor, BOW, CROUCH, FRONT, Fx, SHRUG, type Ink } from "../filmkit";
import type { Running, Script } from "../film-layer";
import { STAND, smooth } from "../rig";

type L = {
  el: HTMLSpanElement;
  left: number;
  right: number;
  cx: number;
  top: number;
  base: number;
  capH: number;
  scale: Spring; // x = scaleY - 1
  lift: Spring; // x = translateY
  target: number; // scaleY target
};

let played = false;

function letters() {
  return [...document.querySelectorAll<HTMLSpanElement>("[data-wordmark] [data-letter]")];
}

function measure(): { ls: L[]; capH: number } | null {
  const els = letters();
  if (els.length < 5) return null;
  const cs = getComputedStyle(els[0]!);
  const ctx = document.createElement("canvas").getContext("2d");
  if (!ctx) return null;
  ctx.font = `${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
  const m = ctx.measureText("R");
  const sy = window.scrollY;
  const capH = m.actualBoundingBoxAscent;
  const ls = els.map((el) => {
    const r = el.getBoundingClientRect();
    const t = el.firstChild;
    const range = document.createRange();
    if (t) range.selectNodeContents(t);
    const rr = t ? range.getBoundingClientRect() : r;
    const base = rr.top + m.fontBoundingBoxAscent + sy;
    const ink = ctx.measureText(el.textContent ?? "R");
    return {
      el,
      left: rr.left + ink.actualBoundingBoxLeft * -1,
      right: rr.left + ink.actualBoundingBoxRight,
      cx: rr.left + (ink.actualBoundingBoxRight - ink.actualBoundingBoxLeft) / 2,
      top: base - capH,
      base,
      capH,
      scale: new Spring(340, 13),
      lift: new Spring(300, 11),
      target: 1,
    };
  });
  return { ls, capH };
}

export const pixar: Script = {
  name: "pixar",
  idleAfter: 2.2,
  priority: 10,
  ready: () => {
    if (played) return false;
    const wm = document.querySelector<HTMLElement>("[data-wordmark]");
    if (!wm) return false;
    const r = wm.getBoundingClientRect();
    return r.top > 40 && r.bottom < window.innerHeight + 10 && r.height > 60;
  },
  start: (): Running => {
    played = true;
    const got = measure()!;
    const { ls, capH } = got;
    const [, , , A, Y] = ls as [L, L, L, L, L];
    const base = ls[0]!.base;
    const H = Math.max(56, Math.min(140, capH * 0.42));
    const a = new Actor(H, window.innerWidth + H, base, -1);
    const fx = new Fx();
    let st = "hop";
    let t = 0;
    let rippleT = 0;
    let crouchT = 0;
    let hops = 0;
    let on: L | null = null; // the letter he stands on
    const go = (s: string) => {
      st = s;
      t = 0;
    };
    const topOf = (l: L) => l.base - l.capH * (1 + l.scale.x) + l.lift.x;
    const write = () => {
      for (const l of ls) {
        const sy = 1 + l.scale.x;
        const sx = sy < 1 ? 1 + (1 - sy) * 0.55 : 1 - (sy - 1) * 0.35;
        l.el.style.transform =
          Math.abs(l.scale.x) < 0.002 && Math.abs(l.lift.x) < 0.2
            ? ""
            : `translateY(${l.lift.x.toFixed(1)}px) scale(${sx.toFixed(3)}, ${sy.toFixed(3)})`;
      }
    };
    for (const l of ls) l.el.style.transformOrigin = "50% 100%";

    /** Luxo hop towards x: crouch, spring, land. Returns true when there. */
    const hopTo = (x: number, dt: number, len = 1.35 * H) => {
      if (a.arc) {
        const land = a.fly(dt);
        if (land !== null) {
          fx.dust(a.x, a.y, 0.45);
          crouchT = 0;
        }
        return false;
      }
      if (Math.abs(x - a.x) < 4) return true;
      crouchT += dt;
      a.settle(CROUCH, dt, 16);
      if (crouchT > 0.16) {
        const step = Math.sign(x - a.x) * Math.min(len, Math.abs(x - a.x));
        a.jump(a.x + step, a.y, 0.55 * H);
      }
      return false;
    };

    const step = (dt: number) => {
      t += dt;
      fx.step(dt);
      for (const l of ls) {
        l.scale.step(dt, l.target - 1);
        l.lift.step(dt);
      }
      let shot: Parameters<Actor["pose2joints"]>[1] = {};
      a.thumb = false;
      switch (st) {
        case "hop":
          if (hopTo(Y.right + 0.9 * H, dt)) go("lookY");
          break;
        case "lookY":
          a.turnTo(-1, dt);
          a.settle({ ...STAND, head: -0.45, lean: -0.05 }, dt);
          shot = { gaze: { x: -0.04 * H, y: -0.05 * H } };
          if (t > 0.9) go("lookYou");
          break;
        case "lookYou":
          a.turnTo(0, dt);
          a.settle({ ...FRONT, head: 0.18 * Math.sin(t * 3) }, dt);
          if (t > 1.0) go("climb");
          break;
        case "climb":
          if (!a.arc) {
            a.settle(CROUCH, dt, 14);
            if (t > 0.25) a.jump(Y.cx + (Y.right - Y.cx) * 0.55, topOf(Y), 0.6 * H);
            break;
          }
          if (a.fly(dt) !== null) {
            on = Y;
            Y.scale.kick(-1.4);
            fx.dust(a.x, a.y, 0.6);
            hops = 0;
            go("bounce");
          }
          break;
        case "bounce":
          if (!a.arc) {
            a.settle(CROUCH, dt, 16);
            if (t > 0.18) {
              hops++;
              a.jump(a.x, topOf(Y), hops >= 3 ? 1.15 * H : 0.45 * H);
            }
          } else if (a.fly(dt) !== null) {
            t = 0;
            if (hops >= 3) {
              // the stomp: the Y gives way
              Y.target = 0.1;
              Y.scale.kick(-3.5);
              fx.dust(a.x, Y.base, 1.2);
              fx.sparks(a.x, a.y, 0.7, -Math.PI / 2, Math.PI);
              knock(Y.el.closest("footer"), { y: 160 }, 1.2);
              go("oops");
            } else {
              Y.scale.kick(-1.6 - hops * 0.5);
            }
          }
          if (!a.arc) a.y = topOf(Y);
          break;
        case "oops":
          a.y = topOf(Y);
          if (t < 0.8) {
            a.settle({ ...STAND, head: 0.55, lean: 0.12 }, dt);
          } else {
            a.turnTo(0, dt);
            a.settle(SHRUG, dt, 8);
          }
          if (t > 2.1) go("tramp");
          break;
        case "tramp":
          a.y = topOf(Y);
          if (!a.arc) {
            a.settle(CROUCH, dt, 14);
            if (t > 0.28) {
              // the Y springs back and throws him: a backflip to the point of the A
              Y.target = 1;
              Y.scale.kick(9);
              a.jump(A.cx, topOf(A), 2.4 * H);
              a.f = -1;
              fx.dust(a.x, a.y, 0.8);
              on = null;
            }
            break;
          }
          {
            const arcT = a.arc;
            a.fly(dt);
            a.rot = arcT ? -Math.PI * 2 * smooth(arcT.t / arcT.T) * Math.sign(a.f || -1) : 0;
            if (!a.arc) {
              a.rot = 0;
              on = A;
              A.scale.kick(-1.2);
              fx.dust(a.x, a.y, 0.5);
              go("balance");
            }
          }
          break;
        case "balance":
          a.y = topOf(A);
          a.turnTo(0, dt);
          a.settle(
            {
              ...FRONT,
              lean: 0.06 * Math.sin(t * 5),
              head: -0.1,
              hipB: 0.9,
              kneeB: 1.3,
              shA: 1.57 + 0.15 * Math.sin(t * 5),
              elA: 0.1,
              shB: 1.57 - 0.15 * Math.sin(t * 5),
              elB: 0.1,
            },
            dt,
            8,
          );
          if (t > 1.5) go("bow");
          break;
        case "bow":
          a.y = topOf(A);
          a.turnTo(0, dt);
          a.settle(t < 0.9 ? BOW : FRONT, dt, 7);
          if (t > 1.5) go("ripple");
          break;
        case "ripple":
          // applause: the letters jump in turn
          rippleT += dt;
          ls.forEach((l, i) => {
            const at = i * 0.11;
            if (rippleT - dt < at && rippleT >= at) l.lift.kick(-520);
          });
          a.y = topOf(A);
          a.settle({ ...FRONT, shA: 2.7, elA: 0.2, shB: 2.7, elB: 0.2, head: -0.2 }, dt, 10);
          if (t > 1.6) go("off");
          break;
        case "off":
          if (!a.arc && t < 0.3) {
            a.settle(CROUCH, dt, 14);
            break;
          }
          if (!a.arc && on) {
            a.jump(A.left - 1.1 * H, base, 0.6 * H);
            on = null;
          }
          if (a.arc) {
            if (a.fly(dt) !== null) {
              fx.dust(a.x, base, 0.8);
              crouchT = 0;
              go("leave");
            }
          }
          break;
        case "leave":
          if (hopTo(-1.5 * H, dt, 1.5 * H)) return true;
          if (a.x < -H) return true;
          break;
      }
      a.pose2joints(dt, shot);
      write();
      return false;
    };

    return {
      step,
      draw: (ctx: CanvasRenderingContext2D, ink: Ink) => {
        const ground = on ? topOf(on) : base;
        a.draw(ctx, ink, a.rot ? undefined : ground);
        fx.draw(ctx, ink);
      },
      cleanup: () => {
        for (const l of ls) l.el.style.transform = "";
      },
    };
  },
};
