/**
 * Dominoes: a figure walks in along the baseline of a big heading, eyes the first word, gives
 * the reader a look, and flicks it. The words of the line topple into each other like rods
 * pivoting on their bottom corners (θ'' = 3g/2h · sin θ), each passing its momentum on and coming
 * to rest leaning on the next; the last one falls flat and bounces. Hands on head, a snap of
 * the fingers, and they spring back up one after another. A bow, and he walks off.
 */

import { Spring } from "../physics";
import { Actor, BOW, FRONT, Fx, G, wrapWords, type Ink } from "../filmkit";
import type { Running, Script } from "../film-layer";
import { STAND, smooth } from "../rig";

type W = {
  el: HTMLSpanElement;
  left: number;
  right: number;
  top: number;
  bottom: number;
  h: number;
  a: number;
  w: number;
  state: "up" | "fall" | "lean" | "flat" | "back";
  back: Spring;
};

function pick(): HTMLElement | null {
  for (const h of document.querySelectorAll<HTMLElement>("main h2")) {
    if (h.querySelector("[data-film-word], [data-film-letter]")) continue;
    const fs = parseFloat(getComputedStyle(h).fontSize);
    if (fs < 36) continue;
    const r = h.getBoundingClientRect();
    if (r.top < 120 || r.bottom > window.innerHeight - 60 || r.left < 60) continue;
    if ((h.textContent ?? "").trim().split(/\s+/).length < 4) continue;
    return h;
  }
  return null;
}

export const dominoes: Script = {
  name: "dominoes",
  idleAfter: 9,
  ready: () => !!pick(),
  start: (): Running => {
    const h2 = pick()!;
    const { spans, restore } = wrapWords(h2);
    const sy = window.scrollY;
    const rects = spans.map((s) => s.getBoundingClientRect());
    const top0 = Math.min(...rects.map((r) => r.top));
    const ws: W[] = spans
      .map((el, i) => ({ el, r: rects[i]! }))
      .filter(({ r }) => Math.abs(r.top - top0) < 6)
      .map(({ el, r }) => ({
        el,
        left: r.left,
        right: r.right,
        top: r.top + sy,
        bottom: r.bottom + sy,
        h: r.height,
        a: 0,
        w: 0,
        state: "up" as const,
        back: new Spring(260, 10),
      }));
    for (const w of ws) w.el.style.transformOrigin = "100% 88%";
    const ground = ws[0]!.bottom - ws[0]!.h * 0.12;
    const H = Math.max(60, Math.min(110, ws[0]!.h * 1.15));
    const a = new Actor(H, -H, ground, 1);
    const fx = new Fx();
    let st = "walk";
    let t = 0;
    const go = (s: string) => {
      st = s;
      t = 0;
    };
    const first = ws[0]!;

    const physics = (dt: number) => {
      ws.forEach((w, i) => {
        const next = ws[i + 1];
        if (w.state === "fall") {
          // a rod pivoting on its foot, a little slowed so it reads
          const alpha = ((3 * G) / (2 * w.h)) * Math.sin(Math.max(0.02, w.a)) * 0.55;
          w.w += alpha * dt;
          w.a += w.w * dt;
          if (next && next.state === "up") {
            const reachX = w.right + w.h * Math.sin(w.a) * 0.9;
            if (reachX >= next.left) {
              next.state = "fall";
              next.w = Math.max(w.w * 0.8, 1.2);
              next.a = 0.02;
              w.state = "lean";
            }
          }
          if (!next && w.a >= Math.PI / 2) {
            w.a = Math.PI / 2;
            if (Math.abs(w.w) > 1.2) {
              w.w = -w.w * 0.28;
              fx.dust(w.right + w.h * 0.8, ground, Math.min(1, w.h / 90));
            } else {
              w.w = 0;
              w.state = "flat";
            }
          }
        } else if (w.state === "lean" && next) {
          // rests against the next word as it goes over
          const gap = next.left - w.right;
          const lean = Math.asin(
            Math.min(1, (gap + next.h * Math.sin(next.a) * 0.95) / (w.h * 0.9)),
          );
          w.a += (lean - w.a) * Math.min(1, dt * 30);
        } else if (w.state === "back") {
          w.back.step(dt, 0);
          w.a = w.back.x;
        }
      });
    };

    const step = (dt: number) => {
      t += dt;
      fx.step(dt);
      physics(dt);
      let shot: Parameters<Actor["pose2joints"]>[1] = {};
      switch (st) {
        case "walk":
          if (a.walkTo(first.left - 0.55 * H, 1.25 * H, dt)) go("eye");
          break;
        case "eye":
          a.turnTo(1, dt);
          a.settle({ ...STAND, lean: 0.18, head: 0.15 }, dt);
          if (t > 0.8 && t < 1.5) {
            a.turnTo(0, dt * 2);
            a.settle({ ...FRONT, head: -0.1, lean: -0.05 }, dt);
          }
          if (t > 1.8) go("poke");
          break;
        case "poke": {
          a.turnTo(1, dt);
          a.settle({ ...STAND, lean: 0.12 }, dt);
          const k = Math.min(1, t / 0.35);
          shot = {
            reachA: {
              target: { x: first.left + 2, y: first.top + first.h * 0.3 },
              w: smooth(k),
              bend: -1,
            },
          };
          if (t > 0.35 && first.state === "up") {
            first.state = "fall";
            first.w = 2.4;
            first.a = 0.03;
            fx.sparks(first.left, first.top + first.h * 0.3, 0.25, 0, 1);
          }
          if (t > 0.6) go("watch");
          break;
        }
        case "watch":
          a.turnTo(1, dt);
          a.settle({ ...STAND, lean: -0.05, head: -0.05 }, dt);
          if (ws[ws.length - 1]!.state === "flat" || t > 6) go("oops");
          break;
        case "oops": {
          a.turnTo(0, dt);
          a.settle({ ...FRONT, head: 0.15 }, dt);
          const j = a.j;
          if (j)
            shot = {
              reachA: { target: { x: j.head.x - 0.08 * H, y: j.head.y - 0.03 * H }, w: 1 },
              reachB: { target: { x: j.head.x + 0.08 * H, y: j.head.y - 0.03 * H }, w: 1 },
            };
          if (t > 1.3) go("snap");
          break;
        }
        case "snap": {
          a.turnTo(0, dt);
          a.settle({ ...FRONT, shA: 2.2, elA: 0.6 }, dt, 12);
          if (t > 0.35 && t - dt <= 0.35 && a.j) {
            fx.sparks(a.j.handA.x, a.j.handA.y, 0.4);
            fx.ring(a.j.handA.x, a.j.handA.y, 18);
          }
          // they spring back up, last first
          ws.slice()
            .reverse()
            .forEach((w, i) => {
              const at = 0.4 + i * 0.09;
              if (t - dt < at && t >= at) {
                w.state = "back";
                w.back.x = w.a;
                w.back.v = -2;
              }
            });
          if (t > 0.6 + ws.length * 0.09) go("bow");
          break;
        }
        case "bow":
          a.turnTo(0, dt);
          a.settle(t < 0.8 ? BOW : FRONT, dt, 7);
          if (t > 1.4) go("leave");
          break;
        case "leave":
          if (a.walkTo(-1.2 * H, 1.3 * H, dt)) return true;
          break;
      }
      a.pose2joints(dt, shot);
      for (const w of ws)
        w.el.style.transform = Math.abs(w.a) < 0.002 ? "" : `rotate(${w.a.toFixed(3)}rad)`;
      return false;
    };

    return {
      step,
      draw: (ctx: CanvasRenderingContext2D, ink: Ink) => {
        a.draw(ctx, ink, ground);
        fx.draw(ctx, ink);
      },
      cleanup: () => {
        for (const w of ws) w.el.style.transform = "";
        restore();
      },
    };
  },
};
