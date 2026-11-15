/**
 * Lights out: a rope drops from the top of the screen beside the theme switch and a figure
 * rappels down it, braking to a stop next to the button. He looks at it, looks at the reader,
 * a finger to his lips, and presses it: the page really goes dark. Out comes a flashlight; he
 * sweeps it across the page, chuckles, switches the lights back on, gives a thumbs up and climbs
 * back up hand over hand. If the film is cut short the theme is always put back.
 */

import { Actor, Fx, hang, reach, type Ink } from "../filmkit";
import type { Running, Script } from "../film-layer";
import { smooth } from "../rig";

const button = () =>
  document.querySelector<HTMLButtonElement>('header button[aria-label^="Switch to"]');
const isDark = () => document.documentElement.classList.contains("dark");

export const lights: Script = {
  name: "lights",
  idleAfter: 10,
  fixed: true,
  ready: () => {
    const b = button();
    if (!b || window.innerWidth < 900) return false;
    const r = b.getBoundingClientRect();
    return r.width > 0 && r.top >= 0;
  },
  start: (): Running => {
    const H = 88;
    const b = button()!;
    const br = b.getBoundingClientRect();
    const startDark = isDark();
    let flipped = false;
    const ropeX = br.left - 0.5 * H;
    const stopHand = br.top + br.height / 2 - 0.32 * H;
    const a = new Actor(H, ropeX, -2 * H, 1);
    const fx = new Fx();
    let st = "drop";
    let t = 0;
    const go = (s: string) => {
      st = s;
      t = 0;
    };
    let ropeEnd = -10;
    let handY = -1.4 * H;
    let vy = 0;
    let torch = 0;
    let torchAng = 0;
    const press = () => {
      b.click();
      flipped = !flipped;
      fx.sparks(br.left + br.width / 2, br.top + br.height / 2, 0.35);
    };

    const step = (dt: number) => {
      t += dt;
      fx.step(dt);
      let shot: Parameters<Actor["pose2joints"]>[1] = {};
      let sway = 0;
      switch (st) {
        case "drop":
          ropeEnd = -10 + (stopHand + 1.1 * H + 10) * smooth(t / 0.55);
          if (t > 0.6) go("rappel");
          break;
        case "rappel": {
          // slide down the rope (gravity, a light grip), then clamp down: a constant braking
          // deceleration chosen to stop exactly beside the button
          const brakeFrom = stopHand - 0.9 * H;
          if (handY < brakeFrom) {
            vy += 1500 * dt;
            handY += vy * dt;
          } else {
            const dist = Math.max(1, stopHand - handY);
            const decel = (vy * vy) / (2 * dist);
            vy = Math.max(0, vy - decel * dt);
            handY += vy * dt;
            if (vy < 25 || handY >= stopHand - 0.5) {
              handY = stopHand;
              vy = 0;
              go("look");
            }
          }
          break;
        }
        case "look":
          sway = 0.08 * Math.exp(-t * 2) * Math.sin(t * 7);
          if (t > 0.7 && t < 1.5) a.f = 0.0001;
          else a.f = 1;
          if (t > 1.8) go("shh");
          break;
        case "shh":
          a.f = 0.0001;
          if (t > 1.2) go("press");
          break;
        case "press":
          a.f = 1;
          if (t > 0.35 && !flipped) press();
          if (t > 0.9) go("dark");
          break;
        case "dark":
          a.f = 1;
          torch = Math.min(1, t / 0.4);
          torchAng = Math.PI * 0.75 + Math.sin(t * 1.3) * 0.55;
          if (t > 3.0) go("laugh");
          break;
        case "laugh":
          a.f = 0.0001;
          torch = Math.max(0, 1 - t / 0.3);
          if (t > 1.0) go("press2");
          break;
        case "press2":
          a.f = 1;
          if (t > 0.35 && flipped) press();
          if (t > 0.9) go("thumbs");
          break;
        case "thumbs":
          a.f = 0.0001;
          a.thumb = t > 0.25;
          if (t > 1.2) {
            a.thumb = false;
            go("climb");
          }
          break;
        case "climb":
          a.f = 1;
          handY -= 1.4 * H * dt;
          if (handY < -1.6 * H) {
            ropeEnd -= 900 * dt;
            if (ropeEnd < -10) return true;
          }
          break;
      }
      // he hangs from the rope by one hand; the other is free
      const hand = { x: ropeX, y: handY };
      const pelvisY = hang(a, hand, sway, { hipA: 0.5, kneeA: 0.9, hipB: 0.2, kneeB: 0.6 });
      a.pose = { ...a.pose, shB: 0.3, elB: 0.3 };
      const j = a.j;
      let free = undefined as ReturnType<typeof reach> | undefined;
      if (st === "shh" && j) free = reach({ x: j.head.x + 0.02 * H, y: j.head.y + 0.05 * H });
      if ((st === "press" || st === "press2") && t < 0.6)
        free = reach(
          { x: br.left + br.width * 0.45, y: br.top + br.height * 0.5 },
          smooth(t / 0.3),
        );
      if (st === "dark" && j)
        free = reach({
          x: j.chest.x + Math.cos(torchAng) * 0.3 * H,
          y: j.chest.y + Math.sin(torchAng) * 0.3 * H,
        });
      if (st === "laugh")
        a.pose = {
          ...a.pose,
          lean: a.pose.lean + 0.06 * Math.sin(t * 30),
          head: a.pose.head - 0.15,
        };
      if (st === "thumbs") free = reach({ x: ropeX + 0.35 * H, y: handY + 0.15 * H });
      if (st === "climb") {
        // hand over hand: the free hand reaches above, then they swap
        const beat = (t * 2.2) % 1;
        free = reach({ x: ropeX, y: handY - 0.18 * H * smooth(beat) });
      }
      shot = { pelvisY, reachA: reach(hand), reachB: free };
      a.pose2joints(dt, shot);
      return false;
    };

    return {
      step,
      draw: (ctx: CanvasRenderingContext2D, ink: Ink) => {
        // the rope
        ctx.strokeStyle = ink.ink;
        ctx.lineWidth = 2;
        ctx.lineCap = "round";
        ctx.beginPath();
        ctx.moveTo(ropeX, -10);
        ctx.lineTo(ropeX + Math.sin(t * 2) * 1.5, ropeEnd);
        ctx.stroke();
        // the flashlight's beam
        if (torch > 0 && a.j) {
          const h = a.j.handB;
          const len = Math.max(window.innerWidth, window.innerHeight) * 0.7;
          const spread = 0.32;
          const g = ctx.createRadialGradient(h.x, h.y, 4, h.x, h.y, len);
          g.addColorStop(0, `rgba(255,244,214,${0.42 * torch})`);
          g.addColorStop(1, "rgba(255,244,214,0)");
          ctx.fillStyle = g;
          ctx.beginPath();
          ctx.moveTo(h.x, h.y);
          ctx.arc(h.x, h.y, len, torchAng - spread, torchAng + spread);
          ctx.closePath();
          ctx.fill();
          ctx.strokeStyle = ink.accent;
          ctx.lineWidth = 0.05 * H;
          ctx.beginPath();
          ctx.moveTo(h.x, h.y);
          ctx.lineTo(h.x + Math.cos(torchAng) * 0.14 * H, h.y + Math.sin(torchAng) * 0.14 * H);
          ctx.stroke();
        }
        if (st !== "drop") a.draw(ctx, ink);
        fx.draw(ctx, ink);
      },
      cleanup: () => {
        // the lights always come back on
        if (isDark() !== startDark) button()?.click();
      },
    };
  },
};
