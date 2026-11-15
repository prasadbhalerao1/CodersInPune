/**
 * The paper plane: a figure walks in, takes a sheet from his pocket and folds it into a plane,
 * licks a finger to test the wind, glances at the reader and throws. The plane is a glider:
 * lift grows with the square of its speed, so thrown fast it climbs, slows, noses over and
 * dives, porpoising across the page; it bonks off the edges of the screen and skids to a stop
 * on the floor or a card. He runs after it, picks it up, shows it off, launches it off-screen,
 * waves and walks away.
 */

import {
  Actor,
  FRONT,
  Fx,
  G,
  THUMB,
  cardTops,
  clamp01,
  reach,
  type Ink,
  type Vec,
} from "../filmkit";
import { wave } from "../gestures";
import type { Running, Script } from "../film-layer";
import { STAND, smooth } from "../rig";

const sizeH = () => (window.innerWidth < 640 ? 70 : 96);

export const plane: Script = {
  name: "plane",
  idleAfter: 9,
  ready: () => window.innerHeight > 520 && window.innerWidth > 700,
  start: (): Running => {
    const H = sizeH();
    const sy = window.scrollY;
    const floor = sy + window.innerHeight - 10;
    const side = (Math.floor(performance.now()) % 2) * 2 - 1; // which edge he comes from
    const a = new Actor(H, side < 0 ? -H : window.innerWidth + H, floor, side < 0 ? 1 : -1);
    const fx = new Fx();
    let st = "walk";
    let t = 0;
    const go = (s: string) => {
      st = s;
      t = 0;
    };
    // the plane
    let fold = 0; // 0 sheet .. 1 plane
    const p = { x: 0, y: 0, vx: 0, vy: 0, ang: 0, landed: false, held: true, gone: false };
    const v0 = 6.2 * H; // trim speed: lift equals weight
    let groundY = floor;
    let bonks = 0;
    const lands = cardTops(floor - 2.3 * H, floor - 0.2 * H);

    const fly = (dt: number) => {
      const sp = Math.hypot(p.vx, p.vy) || 1;
      const dir = Math.sign(p.vx) || 1;
      // "up" for the plane is perpendicular to its velocity, on its top side
      const nx = dir > 0 ? p.vy / sp : -p.vy / sp;
      const ny = dir > 0 ? -p.vx / sp : p.vx / sp;
      const q = (sp / v0) ** 2;
      const lift = G * q * 0.98;
      const drag = G * q * 0.07;
      let ax = nx * lift - (p.vx / sp) * drag;
      let ay = G + ny * lift - (p.vy / sp) * drag;
      // keep it from flipping onto its back in a loop that never ends
      if (ny > 0.2) {
        ax *= 0.6;
        ay = G;
      }
      p.vx += ax * dt;
      p.vy += ay * dt;
      p.x += p.vx * dt;
      p.y += p.vy * dt;
      p.ang = Math.atan2(p.vy, p.vx);
      const top = window.scrollY + 90;
      if (p.y < top) {
        p.y = top;
        p.vy = Math.abs(p.vy) * 0.3;
      }
      if (!p.gone && (p.x < 12 || p.x > window.innerWidth - 12) && bonks < 2) {
        bonks++;
        p.x = Math.max(12, Math.min(window.innerWidth - 12, p.x));
        p.vx = -p.vx * 0.45;
        p.vy *= 0.5;
        fx.sparks(p.x, p.y, 0.35, p.vx > 0 ? 0 : Math.PI, 1.4);
      }
      // touchdown: only from above, on the floor or a low card
      if (p.vy > 0 && !p.gone) {
        for (const c of lands) {
          if (p.x > c.left && p.x < c.right && p.y >= c.y && p.y - p.vy * dt < c.y) {
            p.y = c.y;
            groundY = c.y;
            p.landed = true;
          }
        }
        if (p.y >= floor) {
          p.y = floor;
          groundY = floor;
          p.landed = true;
        }
        if (p.landed) fx.dust(p.x, p.y, 0.3);
      }
    };
    const skid = (dt: number) => {
      p.vx *= Math.exp(-dt * 5);
      p.x += p.vx * dt;
      p.vy = 0;
      p.ang += (Math.sign(p.vx) * 0.12 - p.ang) * Math.min(1, dt * 8);
      p.x = Math.max(12, Math.min(window.innerWidth - 12, p.x));
    };

    const spot = side < 0 ? window.innerWidth * 0.22 : window.innerWidth * 0.78;

    const step = (dt: number) => {
      t += dt;
      fx.step(dt);
      let shot: Parameters<Actor["pose2joints"]>[1] = {};
      const hold = (dx: number, dy: number) => ({ x: a.x + a.f * dx * H, y: a.y - dy * H });
      switch (st) {
        case "walk":
          if (a.walkTo(spot, 1.25 * H, dt)) go("fold");
          break;
        case "fold": {
          // out of the pocket, then folded in front of the chest, hands busy
          a.turnTo(-side, dt);
          a.settle({ ...STAND, head: 0.35, lean: 0.06 }, dt);
          if (t < 0.5)
            shot = { reachA: reach({ x: a.x + a.f * 0.1 * H, y: a.y - 0.42 * H }, smooth(t * 3)) };
          else {
            fold = clamp01((t - 0.6) / 1.3);
            const jig = Math.sin(t * 18) * 0.03;
            shot = { reachA: reach(hold(0.3 + jig, 0.78)), reachB: reach(hold(0.22 - jig, 0.74)) };
          }
          if (t > 2.0) go("wind");
          break;
        }
        case "wind": {
          // lick a finger, hold it up, think, glance at the reader
          a.turnTo(t > 1.3 && t < 1.9 ? 0 : -side, dt);
          a.settle({ ...STAND, head: t < 0.5 ? 0.1 : -0.25 }, dt);
          const j = a.j;
          if (t < 0.5 && j)
            shot = {
              reachA: reach({ x: j.head.x + a.f * 0.1 * H, y: j.head.y + 0.05 * H }),
              reachB: reach(hold(0.28, 0.6)),
            };
          else shot = { reachA: reach(hold(0.15, 1.35)), reachB: reach(hold(0.28, 0.6)) };
          if (t > 2.1) go("throw");
          break;
        }
        case "throw": {
          a.turnTo(-side, dt);
          const wind = t < 0.3;
          a.settle(
            wind
              ? { ...STAND, lean: -0.15, hipA: 0.35, kneeA: 0.3, hipB: -0.35, kneeB: 0.15 }
              : { ...STAND, lean: 0.3, hipA: 0.45, kneeA: 0.35, hipB: -0.45, kneeB: 0.1 },
            dt,
            18,
          );
          shot = { reachB: reach(wind ? hold(-0.25, 1.05) : hold(0.6, 1.1)) };
          if (!wind && p.held) {
            const j = a.j!;
            p.held = false;
            p.x = j.handB.x;
            p.y = j.handB.y;
            p.vx = a.f * 8.4 * H;
            p.vy = -4.4 * H;
          }
          if (!p.held) {
            fly(dt);
            if (t > 0.5) go("watch");
          }
          break;
        }
        case "watch": {
          // follow it with a hand shading the eyes
          if (!p.landed) fly(dt);
          else skid(dt);
          a.turnTo(Math.sign(p.x - a.x) || a.f, dt);
          a.settle({ ...STAND, head: p.y < a.y - 2 * H ? -0.35 : 0 }, dt);
          const j = a.j;
          if (j) shot = { reachA: reach({ x: j.head.x + a.f * 0.12 * H, y: j.head.y - 0.06 * H }) };
          if ((p.landed && Math.abs(p.vx) < 15) || t > 9) go("chase");
          break;
        }
        case "chase": {
          if (groundY < floor - 1 && !a.arc && a.y >= floor - 1 && Math.abs(p.x - a.x) < 1.5 * H) {
            a.jump(p.x - a.f * 0.45 * H, groundY, 0.5 * H);
          }
          if (a.arc) {
            if (a.fly(dt) !== null) fx.dust(a.x, a.y, 0.6);
            break;
          }
          const dist = Math.abs(p.x - a.x);
          if (
            a.walkTo(
              p.x - Math.sign(p.x - a.x || 1) * 0.45 * H,
              dist > 3 * H ? 5 * H : 2.2 * H,
              dt,
            ) &&
            Math.abs(a.y - groundY) < 2
          )
            go("pick");
          break;
        }
        case "pick": {
          a.turnTo(Math.sign(p.x - a.x) || a.f, dt);
          const k = t / 0.9;
          const down = k < 0.45 ? smooth(k / 0.45) : 1 - smooth((k - 0.55) / 0.45);
          a.settle(
            {
              ...STAND,
              lean: 0.55 * down,
              head: 0.35 * down,
              hipA: 0.15 + 1.1 * down,
              kneeA: 0.1 + 1.9 * down,
              hipB: 0.8 * down,
              kneeB: 1.7 * down,
            },
            dt,
            14,
          );
          if (k > 0.45) p.held = true;
          shot = {
            reachB: reach(
              p.held && a.j ? hold(0.3, 0.25 + 0.6 * (1 - down)) : { x: p.x, y: p.y - 4 },
            ),
          };
          if (k >= 1) go("show");
          break;
        }
        case "show": {
          // hold it up to the reader
          a.turnTo(0, dt);
          a.settle({ ...THUMB, shB: 2.4, elB: 0.4 }, dt);
          a.thumb = t > 0.3;
          shot = { reachB: reach({ x: a.x + 0.25 * H, y: a.y - 1.25 * H }) };
          if (t > 1.4) go("relaunch");
          break;
        }
        case "relaunch": {
          a.thumb = false;
          const out = a.x > window.innerWidth / 2 ? 1 : -1;
          a.turnTo(out, dt);
          a.settle(t < 0.25 ? { ...STAND, lean: -0.15 } : { ...STAND, lean: 0.3 }, dt, 18);
          shot = { reachB: reach(t < 0.25 ? hold(-0.25, 1.05) : hold(0.6, 1.15)) };
          if (t >= 0.25 && p.held) {
            const j = a.j!;
            p.held = false;
            p.landed = false;
            p.gone = true;
            p.x = j.handB.x;
            p.y = j.handB.y;
            p.vx = out * 8 * H;
            p.vy = -2.2 * H;
          }
          if (!p.held) fly(dt);
          if (t > 0.8) go("bye");
          break;
        }
        case "bye":
          if (!p.held) fly(dt);
          a.turnTo(0, dt);
          a.settle({ ...FRONT, ...wave(t) }, dt, 12);
          if (t > 1.5) go("leave");
          break;
        case "leave": {
          if (a.y < floor - 1 && !a.arc) a.jump(a.x + a.f * 0.8 * H, floor, 0.4 * H);
          if (a.arc) {
            if (a.fly(dt) !== null) fx.dust(a.x, a.y, 0.5);
            break;
          }
          const out = a.x > window.innerWidth / 2 ? window.innerWidth + 1.2 * H : -1.2 * H;
          if (a.walkTo(out, 1.3 * H, dt)) return true;
          break;
        }
      }
      if (p.held && a.j && st !== "fold" && st !== "wind") {
        p.x = a.j.handB.x;
        p.y = a.j.handB.y;
        p.ang = a.f > 0 ? -0.15 : Math.PI + 0.15;
      } else if (p.held && a.j) {
        p.x = (a.j.handA.x + (a.j.handB?.x ?? a.j.handA.x)) / 2;
        p.y = a.j.handB.y;
        p.ang = a.f > 0 ? 0 : Math.PI;
      }
      a.pose2joints(dt, shot);
      return false;
    };

    const drawPlane = (ctx: CanvasRenderingContext2D, ink: Ink) => {
      const s = 0.38 * H;
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate(p.ang);
      ctx.lineJoin = "round";
      ctx.lineWidth = 1.6;
      ctx.strokeStyle = ink.ink;
      ctx.fillStyle = ink.page;
      if (fold < 1) {
        // the sheet, narrowing into a dart as it is folded
        const w = s * (1 - 0.3 * fold);
        const h = s * 0.75 * (1 - 0.75 * fold);
        ctx.beginPath();
        ctx.moveTo(-w / 2, -h / 2);
        ctx.lineTo(w / 2, (-h / 2) * (1 - fold));
        ctx.lineTo(w / 2, (h / 2) * (1 - fold));
        ctx.lineTo(-w / 2, h / 2);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
      } else {
        const wing: Vec[] = [
          { x: s * 0.5, y: 0 },
          { x: -s * 0.5, y: -s * 0.22 },
          { x: -s * 0.36, y: 0 },
          { x: -s * 0.5, y: s * 0.12 },
        ];
        ctx.beginPath();
        wing.forEach((q, i) => (i ? ctx.lineTo(q.x, q.y) : ctx.moveTo(q.x, q.y)));
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(s * 0.5, 0);
        ctx.lineTo(-s * 0.36, 0);
        ctx.stroke();
      }
      ctx.restore();
    };

    return {
      step,
      draw: (ctx: CanvasRenderingContext2D, ink: Ink) => {
        a.draw(ctx, ink, a.arc ? groundY : a.y);
        if (fold > 0 || !p.held || st === "fold") drawPlane(ctx, ink);
        fx.draw(ctx, ink);
      },
      cleanup: () => {},
    };
  },
};
