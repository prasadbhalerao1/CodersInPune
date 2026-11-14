"use client";

import { useEffect, useRef, useSyncExternalStore } from "react";

import {
  approach,
  clamp01,
  dims,
  gait,
  mix,
  runLift,
  smooth,
  solve,
  stride,
  type Dims,
  type Joints,
  type Pose,
  type Reach,
  type Vec,
} from "./rig";
import { Ragdoll, type Bounds, type Impact, type Plat } from "./ragdoll";
import {
  CROSS,
  GETUP_TIME,
  GUARD,
  JAB,
  KICK,
  TAUNT_TIME,
  UPPERCUT,
  getup,
  idle,
  shakeFist,
  taunt,
  type Strike,
} from "./fight";
import { Spring, knock } from "./physics";
import { FIGURES_ON } from "./stage";

/**
 * The roaming figure: a stick fighter loose on the page, in the spirit of a stick figure who
 * fights the animator's cursor. He lives in document space on one full-viewport canvas:
 *
 * - The top edges of the page's glass cards and buttons are platforms. He walks and runs on
 *   them with a keyed walk/run cycle, jumps between them on ballistic arcs, drops off edges, and
 *   rides the bottom of the viewport as a floor, so he is always on screen as the page scrolls.
 * - The cursor is his opponent. He chases it, jumps to reach it, and throws jabs, crosses,
 *   uppercuts and kicks at it (aimed with IK; sparks where they land), dodges when it lunges at
 *   him, and taunts between rounds.
 * - The viewer can fight back: click him, swipe through him, or grab him by any limb and throw
 *   him. He goes ragdoll (Verlet), slams into cards (which shake from the impact), tumbles,
 *   settles, gets up, and shakes a fist.
 *
 * He never blocks the page: the canvas ignores the pointer, and a press only becomes a grab when
 * it lands on his body.
 */

type Mode = "fall" | "ground" | "ragdoll" | "getup";
type Act = "idle" | "wander" | "chase" | "fight" | "taunt" | "fist";
type Particle = {
  kind: "spark" | "dust" | "ring";
  x: number;
  y: number;
  vx: number;
  vy: number;
  age: number;
  life: number;
  size: number;
};

const GRAVITY = 2600;
const SELECTOR = '.glass, .glass-dark, .glass-clear, [data-fig="cta"], [data-fig="try-cta"]';

type State = {
  t: number;
  H: number;
  d: Dims;
  x: number;
  y: number;
  vx: number;
  vy: number;
  mode: Mode;
  act: Act;
  actT: number;
  plat: Plat | "floor" | null;
  f: number;
  ph: number;
  pose: Pose;
  squash: Spring;
  strike: Strike | null;
  strikeT: number;
  combo: number;
  cooldown: number;
  hits: number;
  dodgeCool: number;
  wanderX: number;
  wanderT: number;
  rag: Ragdoll;
  quiet: number;
  from: Joints | null;
  j: Joints | null;
  plats: Plat[];
  scanT: number;
  ps: Particle[];
  seed: number;
};

type Pointer = {
  x: number;
  y: number;
  cx: number;
  cy: number;
  vx: number;
  vy: number;
  moved: number;
  inside: boolean;
  down: boolean;
  dragging: boolean;
  downAt: number;
  downX: number;
  downY: number;
  hitCool: number;
};

function rnd(s: State) {
  let x = s.seed;
  x ^= x << 13;
  x ^= x >>> 17;
  x ^= x << 5;
  s.seed = x >>> 0;
  return (s.seed % 100000) / 100000;
}

function scan(): Plat[] {
  const out: Plat[] = [];
  const sy = window.scrollY;
  for (const el of document.querySelectorAll<HTMLElement>(SELECTOR)) {
    if (el.closest("header, [data-roamer-skip]")) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 90 || r.height < 24) continue;
    out.push({ el, left: r.left + 6, right: r.right - 6, top: r.top + sy });
  }
  return out;
}

const lerpV = (a: Vec, b: Vec, k: number): Vec => ({
  x: a.x + (b.x - a.x) * k,
  y: a.y + (b.y - a.y) * k,
});
function lerpJ(a: Joints, b: Joints, k: number): Joints {
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
    o[key] = lerpV(a[key], b[key], k);
  }
  return o;
}

function RoamerLayer() {
  const canvas = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const cv = canvas.current;
    const ctx = cv?.getContext("2d");
    if (!cv || !ctx) return;

    let dpr = 1;
    let ink = "#f2eee5";
    let accent = "#b8ff3c";
    let halo = "rgba(4,6,15,0.8)";
    const readColours = () => {
      const cs = getComputedStyle(document.documentElement);
      ink = cs.getPropertyValue("--strong").trim() || ink;
      accent = cs.getPropertyValue("--ac").trim() || accent;
      const page = cs.getPropertyValue("--page").trim() || "#04060f";
      halo = page;
    };
    const fit = () => {
      dpr = Math.min(2, window.devicePixelRatio || 1);
      cv.width = Math.round(window.innerWidth * dpr);
      cv.height = Math.round(window.innerHeight * dpr);
    };
    fit();
    readColours();
    const themeObs = new MutationObserver(readColours);
    themeObs.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });

    const H0 = window.innerWidth < 640 ? 74 : 104;
    const s: State = {
      t: 0,
      H: H0,
      d: dims(H0),
      x: window.innerWidth * 0.74,
      y: window.scrollY + 90,
      vx: -1.2 * H0,
      vy: 0,
      mode: "fall",
      act: "idle",
      actT: 0,
      plat: null,
      f: -1,
      ph: 0,
      pose: GUARD,
      squash: new Spring(300, 15),
      strike: null,
      strikeT: 0,
      combo: 0,
      cooldown: 0,
      hits: 0,
      dodgeCool: 0,
      wanderX: window.innerWidth * 0.5,
      wanderT: 0,
      rag: new Ragdoll(dims(H0)),
      quiet: 0,
      from: null,
      j: null,
      plats: [],
      scanT: 0,
      ps: [],
      seed: 12345,
    };
    const P: Pointer = {
      x: -1e4,
      y: -1e4,
      cx: -1e4,
      cy: -1e4,
      vx: 0,
      vy: 0,
      moved: -10,
      inside: false,
      down: false,
      dragging: false,
      downAt: 0,
      downX: 0,
      downY: 0,
      hitCool: 0,
    };

    // ── effects ──
    const sparks = (
      x: number,
      y: number,
      power: number,
      angle = -Math.PI / 2,
      spread = Math.PI * 2,
    ) => {
      const n = Math.round(8 + 10 * power);
      for (let i = 0; i < n; i++) {
        const a = angle + (rnd(s) - 0.5) * spread;
        const v = (300 + 520 * rnd(s)) * (0.6 + 0.5 * power);
        s.ps.push({
          kind: "spark",
          x,
          y,
          vx: Math.cos(a) * v,
          vy: Math.sin(a) * v,
          age: 0,
          life: 0.2 + 0.2 * rnd(s),
          size: 7 + 9 * rnd(s),
        });
      }
      s.ps.push({ kind: "ring", x, y, vx: 0, vy: 0, age: 0, life: 0.28, size: 18 + 22 * power });
    };
    const dust = (x: number, y: number, power: number) => {
      const n = Math.round(4 + 6 * power);
      for (let i = 0; i < n; i++) {
        const side = i % 2 ? 1 : -1;
        const v = (50 + 140 * rnd(s)) * (0.6 + 0.6 * power);
        s.ps.push({
          kind: "dust",
          x: x + side * 5 * rnd(s),
          y,
          vx: side * v,
          vy: -(20 + 70 * rnd(s)),
          age: 0,
          life: 0.5 + 0.4 * rnd(s),
          size: 3 + 5 * rnd(s) * power,
        });
      }
    };

    // ── the ragdoll's impacts shake whatever it hits ──
    const onImpact = (i: Impact) => {
      const power = Math.min(1.6, i.speed / 1400);
      if (i.plat?.el)
        knock(i.plat.el, { y: Math.min(520, i.speed * 0.28), r: (rnd(s) - 0.5) * 10 * power }, 0.8);
      if (i.speed > 1000) sparks(i.x, i.y, power * 0.7, -Math.PI / 2, Math.PI * 0.9);
      dust(i.x, i.y, power);
    };

    const goRagdoll = (vx: number, vy: number, spin: number) => {
      if (!s.j) return;
      if (s.mode !== "ragdoll") s.rag.fromJoints(s.j, s.vx + vx, s.vy + vy, spin);
      else s.rag.impulse(vx, vy);
      s.mode = "ragdoll";
      s.quiet = 0;
      s.strike = null;
    };

    // ── pointer ──
    const near = (x: number, y: number) => {
      if (s.mode === "ragdoll") return s.rag.nearest(x, y).dist < 0.32 * s.H;
      const j = s.j;
      if (!j) return false;
      const pts = [
        j.head,
        j.chest,
        j.pelvis,
        j.handA,
        j.handB,
        j.kneeA,
        j.kneeB,
        j.footA,
        j.footB,
        j.elbowA,
        j.elbowB,
      ];
      return (
        pts.some((q) => Math.hypot(q.x - x, q.y - y) < 0.28 * s.H) ||
        Math.hypot(j.head.x - x, j.head.y - y) < s.d.head + 8
      );
    };
    let lastMove = 0;
    let cursorSet = "";
    const setCursor = (c: string) => {
      if (c === cursorSet) return;
      cursorSet = c;
      document.documentElement.style.cursor = c;
    };
    const onMove = (e: PointerEvent) => {
      const now = performance.now() / 1000;
      const dtm = Math.max(0.008, now - lastMove);
      lastMove = now;
      const x = e.clientX;
      const y = e.clientY + window.scrollY;
      const vx = (e.clientX - P.cx) / dtm;
      const vy = (e.clientY - P.cy) / dtm;
      const k = 0.5;
      P.vx = P.vx * (1 - k) + vx * k;
      P.vy = P.vy * (1 - k) + vy * k;
      // a fast swipe through him is a hit
      const speed = Math.hypot(P.vx, P.vy);
      if (!P.dragging && speed > 1500 && s.t > P.hitCool && P.inside) {
        const steps = 6;
        for (let i = 0; i <= steps; i++) {
          const qx = P.x + ((x - P.x) * i) / steps;
          const qy = P.y + ((y - P.y) * i) / steps;
          if (near(qx, qy)) {
            P.hitCool = s.t + 0.35;
            goRagdoll(P.vx * 0.5, P.vy * 0.5 - 350, Math.sign(P.vx) * 7);
            sparks(qx, qy, Math.min(1.4, speed / 2200), Math.atan2(P.vy, P.vx), 1.2);
            break;
          }
        }
      }
      P.x = x;
      P.y = y;
      P.cx = e.clientX;
      P.cy = e.clientY;
      P.inside = true;
      P.moved = s.t;
      if (P.dragging) s.rag.pinAt = { x, y };
      else setCursor(near(x, y) ? "grab" : "");
    };
    const onDown = (e: PointerEvent) => {
      const x = e.clientX;
      const y = e.clientY + window.scrollY;
      if (e.button !== 0 || !near(x, y)) return;
      e.preventDefault();
      e.stopPropagation();
      P.down = true;
      P.dragging = true;
      P.downAt = s.t;
      P.downX = x;
      P.downY = y;
      goRagdoll(0, 0, 0);
      s.rag.grab(s.rag.nearest(x, y).index, { x, y });
      setCursor("grabbing");
      // the press was on him, not on the page underneath
      const swallow = (ev: MouseEvent) => {
        ev.preventDefault();
        ev.stopPropagation();
      };
      window.addEventListener("click", swallow, { capture: true, once: true });
      setTimeout(() => window.removeEventListener("click", swallow, { capture: true }), 600);
    };
    const onUp = () => {
      if (!P.dragging) return;
      P.dragging = false;
      P.down = false;
      const quick = s.t - P.downAt < 0.2 && Math.hypot(P.x - P.downX, P.y - P.downY) < 8;
      if (quick) {
        // a click: he takes a punch
        s.rag.release(0, 0);
        const away = Math.sign((s.j?.chest.x ?? P.x) - P.x) || 1;
        s.rag.impulse(away * 1150, -760);
        sparks(P.x, P.y, 1, Math.atan2(-0.6, away), 1.4);
      } else {
        s.rag.release(
          Math.max(-3600, Math.min(3600, P.vx * 0.9)),
          Math.max(-3600, Math.min(3600, P.vy * 0.9)),
        );
      }
      setCursor("");
    };
    const onLeave = () => {
      P.inside = false;
    };
    const onTouch = (e: TouchEvent) => {
      const t0 = e.touches[0];
      if (t0 && near(t0.clientX, t0.clientY + window.scrollY)) e.preventDefault();
    };
    window.addEventListener("pointermove", onMove, { passive: true });
    window.addEventListener("pointerdown", onDown, { capture: true });
    window.addEventListener("pointerup", onUp);
    window.addEventListener("pointercancel", onUp);
    document.addEventListener("pointerleave", onLeave);
    window.addEventListener("touchstart", onTouch, { passive: false });
    window.addEventListener("resize", fit);

    // ── the frame ──
    let raf = 0;
    let last = 0;
    let box = { x0: 0, y0: 0, x1: 0, y1: 0 };
    let tag = 0;
    const frame = (now: number) => {
      const dt = last ? Math.min(0.033, (now - last) / 1000) : 0;
      last = now;
      raf = requestAnimationFrame(frame);
      if (dt === 0) return;
      step(dt);
      draw();
      // where he is and what he is doing, for tests and debugging (5 times a second)
      tag += dt;
      if (tag > 0.2 && s.j) {
        tag = 0;
        cv.dataset.x = s.j.chest.x.toFixed(0);
        cv.dataset.y = (s.j.chest.y - window.scrollY).toFixed(0);
        cv.dataset.mode = s.mode;
        cv.dataset.act = s.act;
        cv.dataset.hits = String(s.hits);
      }
    };

    const supportUnder = (
      x: number,
      y: number,
      b: Bounds,
    ): { top: number; plat: Plat | "floor" } => {
      let best: { top: number; plat: Plat | "floor" } = { top: b.floor, plat: "floor" };
      for (const pl of s.plats) {
        if (x < pl.left || x > pl.right) continue;
        if (pl.top < y - 2 || pl.top < b.ceil + s.H * 0.4 || pl.top > b.floor) continue;
        if (pl.top < best.top) best = { top: pl.top, plat: pl };
      }
      return best;
    };

    const step = (dt: number) => {
      s.t += dt;
      const vw = window.innerWidth;
      const vh = window.innerHeight;
      const sy = window.scrollY;
      const H = vw < 640 ? 74 : 104;
      if (H !== s.H) {
        s.H = H;
        s.d = dims(H);
        s.rag = new Ragdoll(s.d);
      }
      const { d } = s;
      const b: Bounds = { left: 6, right: vw - 6, ceil: sy + 70, floor: sy + vh - 8 };
      s.scanT -= dt;
      if (s.scanT <= 0) {
        s.scanT = 0.45;
        s.plats = scan().filter((p) => p.top > b.ceil - 40 && p.top < b.floor + 40);
      }
      s.squash.step(dt);
      s.cooldown -= dt;
      s.dodgeCool -= dt;

      // particles
      for (const q of s.ps) {
        q.age += dt;
        if (q.kind === "spark") {
          q.vx *= Math.exp(-dt * 6);
          q.vy = q.vy * Math.exp(-dt * 6) + 1100 * dt;
        } else if (q.kind === "dust") {
          q.vx *= Math.exp(-dt * 4);
          q.vy *= Math.exp(-dt * 3);
        }
        q.x += q.vx * dt;
        q.y += q.vy * dt;
      }
      s.ps = s.ps.filter((q) => q.age < q.life);

      // ── ragdoll ──
      if (s.mode === "ragdoll") {
        s.rag.step(dt, s.plats, b, onImpact);
        s.j = s.rag.joints();
        s.quiet = s.rag.pin === null && s.rag.speed() < 70 ? s.quiet + dt : 0;
        if (s.quiet > 0.5) {
          const j = s.j;
          s.from = j;
          s.x = j.pelvis.x;
          const sup = supportUnder(s.x, j.pelvis.y - 0.2 * H, b);
          s.y = sup.top;
          s.plat = sup.plat;
          s.vx = 0;
          s.vy = 0;
          s.mode = "getup";
          s.actT = 0;
          s.f = Math.sign(P.x - s.x) || 1;
        }
        return;
      }

      // ── get up ──
      if (s.mode === "getup") {
        s.actT += dt;
        const target = solve(getup(s.actT), d, s.x, s.y, s.f);
        const k = smooth(s.actT / 0.42);
        s.j = s.from ? lerpJ(s.from, target, k) : target;
        if (s.actT >= GETUP_TIME) {
          s.mode = "ground";
          s.pose = GUARD;
          setAct(P.inside && s.t - P.moved < 4 ? "fist" : "idle");
        }
        return;
      }

      // ── support, gravity, landing ──
      if (s.mode === "ground") {
        if (s.plat === "floor") {
          if (b.floor < s.y) s.y = b.floor;
          else if (b.floor - s.y > 2) s.mode = "fall";
        } else if (s.plat) {
          const el = s.plat.el;
          const live = s.plats.find((p) => p.el === el);
          if (
            !live ||
            s.x < live.left - 4 ||
            s.x > live.right + 4 ||
            live.top > b.floor ||
            live.top < b.ceil
          ) {
            s.mode = "fall";
            s.vy = 0;
          } else {
            s.y = live.top;
            s.plat = live;
          }
        } else s.mode = "fall";
      }
      if (s.mode === "fall") {
        const prevY = s.y;
        s.vy += GRAVITY * dt;
        s.x += s.vx * dt;
        s.y += s.vy * dt;
        if (s.vy > 0) {
          let land: { top: number; plat: Plat | "floor" } | null = null;
          for (const pl of s.plats) {
            if (s.x < pl.left || s.x > pl.right) continue;
            if (prevY <= pl.top && s.y >= pl.top && pl.top > b.ceil + H * 0.4) {
              if (!land || pl.top < land.top) land = { top: pl.top, plat: pl };
            }
          }
          if (!land && s.y >= b.floor) land = { top: b.floor, plat: "floor" };
          if (land) {
            const speed = s.vy;
            s.y = land.top;
            s.vy = 0;
            s.vx *= 0.45;
            s.mode = "ground";
            s.plat = land.plat;
            s.squash.kick(Math.min(7, speed / 140));
            dust(s.x, s.y, Math.min(1.4, speed / 1300));
            if (speed > 1000 && land.plat !== "floor")
              knock(land.plat.el, { y: speed * 0.18 }, 0.9);
          }
        }
      }
      if (s.x < b.left + 0.2 * H) {
        s.x = b.left + 0.2 * H;
        s.vx = Math.abs(s.vx) * 0.3;
      }
      if (s.x > b.right - 0.2 * H) {
        s.x = b.right - 0.2 * H;
        s.vx = -Math.abs(s.vx) * 0.3;
      }

      // ── brain ──
      const recent = P.inside && s.t - P.moved < 3 && P.x > -1e3;
      const dx = P.x - s.x;
      const pointerSpeed = Math.hypot(P.vx, P.vy);
      s.actT += dt;
      let targetX = s.x;
      let speed = 0;
      const grounded = s.mode === "ground";

      if (grounded && !s.strike) {
        const inX = Math.abs(dx) < 1.0 * H;
        const inY = P.y > s.y - 1.4 * H && P.y < s.y - 0.08 * H;
        // a lunge at him: hop back out of the way
        if (
          recent &&
          pointerSpeed > 1700 &&
          Math.hypot(dx, P.y - (s.y - 0.6 * H)) < 1.7 * H &&
          s.dodgeCool <= 0
        ) {
          s.dodgeCool = 1.4;
          jump(0.7 * H, -Math.sign(dx || 1) * 3.4 * H);
        } else if (s.act === "taunt" && s.actT < TAUNT_TIME) {
          // hold the taunt
        } else if (s.act === "fist" && s.actT < 0.9) {
          // shake it
        } else if (recent && inX && inY) {
          setAct("fight");
        } else if (recent) {
          setAct("chase");
          targetX = P.x - Math.sign(dx || 1) * 0.65 * H;
          const far = Math.abs(dx);
          speed = far > 3 * H ? 5.6 * H : far > 1.3 * H ? 3 * H : 1.4 * H;
          // the cursor is up on something: jump for it
          if (P.y < s.y - 1.2 * H && far < 4 * H) {
            const up = s.plats
              .filter(
                (pl) =>
                  P.x > pl.left - H &&
                  P.x < pl.right + H &&
                  pl.top < s.y - 0.4 * H &&
                  pl.top > s.y - 3.2 * H &&
                  pl.top > P.y - 0.4 * H,
              )
              .sort((a, c) => c.top - a.top)[0];
            if (up) {
              const land = Math.max(
                up.left + 0.3 * H,
                Math.min(up.right - 0.3 * H, P.x - Math.sign(dx || 1) * 0.6 * H),
              );
              const rise = s.y - up.top;
              const vy0 = Math.sqrt(2 * GRAVITY * (rise + 0.5 * H));
              const t = vy0 / GRAVITY + Math.sqrt((2 * 0.5 * H) / GRAVITY);
              jump(rise + 0.5 * H, (land - s.x) / t);
            } else if (Math.abs(dx) < 1.2 * H && P.y > s.y - 2.4 * H) {
              // nothing to stand on: jump straight at it
              jump(Math.min(2.2 * H, s.y - P.y), dx * 1.6);
            }
          }
        } else {
          if (s.act !== "wander" && s.act !== "idle") setAct("idle");
          s.wanderT -= dt;
          if (s.wanderT <= 0) {
            s.wanderT = 3 + 4 * rnd(s);
            const pl = s.plat && s.plat !== "floor" ? s.plat : null;
            const lo = pl ? pl.left + 0.4 * H : b.left + H;
            const hi = pl ? pl.right - 0.4 * H : b.right - H;
            s.wanderX = lo + (hi - lo) * rnd(s);
            setAct(rnd(s) < 0.35 ? "idle" : "wander");
          }
          if (s.act === "wander") {
            targetX = s.wanderX;
            speed = 1.3 * H;
          }
        }
      }

      // fight: strikes in combos, aimed at the cursor
      if (grounded && s.act === "fight") {
        if (!s.strike && s.cooldown <= 0) {
          const rel = (s.y - P.y) / H;
          const order: Strike[] =
            rel > 1.05
              ? [JAB, UPPERCUT]
              : rel < 0.55
                ? [KICK, JAB]
                : [JAB, JAB, CROSS, UPPERCUT, KICK];
          s.strike = order[s.combo % order.length]!;
          s.combo++;
          s.strikeT = 0;
        }
      }
      if (s.strike) {
        s.strikeT += dt;
        if (s.strikeT >= s.strike.time) {
          s.strike = null;
          s.cooldown = s.combo % 3 === 0 ? 0.55 : 0.08;
          if (s.hits >= 6) {
            s.hits = 0;
            setAct("taunt");
          }
        }
      }

      // momentum: accelerate to the target speed, brake harder than you accelerate
      if (grounded) {
        const want =
          s.strike || s.act === "fight" || s.act === "taunt" || s.act === "fist"
            ? 0
            : Math.abs(targetX - s.x) < 0.25 * H
              ? 0
              : Math.sign(targetX - s.x) * speed;
        const a =
          Math.sign(want) === Math.sign(s.vx) && Math.abs(want) > Math.abs(s.vx) ? 15 * H : 24 * H;
        const dv = want - s.vx;
        s.vx += Math.sign(dv) * Math.min(Math.abs(dv), a * dt);
        s.x += s.vx * dt;
      }

      // facing
      let fT = s.f;
      if (Math.abs(s.vx) > 0.6 * H) fT = Math.sign(s.vx);
      else if (recent) fT = Math.sign(dx) || s.f;
      s.f += (fT - s.f) * approach(dt, 16);

      // ── pose ──
      const H_ = H;
      let pose: Pose;
      let reachA: Reach | undefined;
      let reachB: Reach | undefined;
      let lift = 0;
      const moving = Math.abs(s.vx) > 0.2 * H_;
      if (s.mode === "fall") {
        const rising = s.vy < 0;
        pose = rising
          ? {
              ...GUARD,
              lean: 0.1,
              head: -0.15,
              hipA: 1.0,
              kneeA: 1.7,
              hipB: 0.45,
              kneeB: 1.4,
              shA: 2.3,
              elA: 0.5,
              shB: 1.7,
              elB: 0.7,
            }
          : {
              ...GUARD,
              lean: -0.05,
              head: 0.15,
              hipA: 0.35,
              kneeA: 0.35,
              hipB: -0.15,
              kneeB: 0.5,
              shA: 2.5,
              elA: 0.3,
              shB: 2.0,
              elB: 0.4,
            };
        s.pose = mix(s.pose, pose, approach(dt, 12));
        pose = s.pose;
      } else if (s.strike) {
        pose = s.strike.pose(s.strikeT);
        const ext = s.strike.extend(s.strikeT);
        if (s.strike.limb === "handA")
          reachA = { target: { x: P.x, y: P.y }, w: ext * 0.97, bend: -1 };
        else if (s.strike.limb === "handB")
          reachB = { target: { x: P.x, y: P.y }, w: ext * 0.97, bend: -1 };
        else {
          // aim the kick: the hip angle that points the leg at the cursor
          const pelvisY = s.y - (d.thigh + d.shin) * 0.9;
          const aim = Math.atan2((P.x - s.x) * Math.sign(s.f || 1), P.y - pelvisY);
          pose = { ...pose, hipA: pose.hipA + (aim - pose.hipA) * ext };
        }
        s.pose = pose;
      } else if (moving) {
        const run = clamp01((Math.abs(s.vx) - 1.3 * H_) / (3.6 * H_));
        s.ph += (2 * Math.PI * Math.abs(s.vx) * dt) / stride(run, H_);
        pose = gait(s.ph, run);
        lift = runLift(s.ph, run, H_, pose, d);
        s.pose = mix(s.pose, pose, approach(dt, 22));
        pose = s.pose;
      } else {
        const base =
          s.act === "fight"
            ? GUARD
            : s.act === "taunt"
              ? taunt(s.actT)
              : s.act === "fist"
                ? shakeFist(s.actT)
                : idle(s.t);
        s.pose = mix(s.pose, base, approach(dt, 12));
        pose = s.pose;
      }
      // landings in the knees
      const sq = Math.max(0, s.squash.x);
      if (sq > 0.01) {
        pose = {
          ...pose,
          hipA: pose.hipA + 0.5 * sq,
          kneeA: pose.kneeA + 0.95 * sq,
          hipB: pose.hipB + 0.45 * sq,
          kneeB: pose.kneeB + 0.9 * sq,
          lean: pose.lean + 0.15 * sq,
        };
      }
      const gaze = recent
        ? {
            x: Math.max(-1, Math.min(1, dx / (3 * H_))) * 0.06 * H_,
            y: Math.max(-1, Math.min(1, (P.y - (s.y - H_)) / (3 * H_))) * 0.04 * H_,
          }
        : undefined;
      const j = solve(pose, d, s.x, s.y, s.f, {
        reachA,
        reachB,
        gaze,
        lift: lift - sq * 0.08 * H_,
      });
      s.j = j;

      // did the strike land?
      if (s.strike) {
        const hitT = s.strike.hit;
        if (s.strikeT - dt < hitT && s.strikeT >= hitT) {
          const limb = s.strike.limb === "footA" ? j.footA : j[s.strike.limb];
          if (Math.hypot(limb.x - P.x, limb.y - P.y) < 0.45 * H_ && P.inside) {
            s.hits++;
            sparks(P.x, P.y, s.strike.power, Math.atan2(P.y - j.chest.y, P.x - j.chest.x), 1.6);
            // whatever the cursor is over takes the hit too
            const under = document.elementFromPoint(P.cx, P.cy)?.closest<HTMLElement>(SELECTOR);
            if (under)
              knock(
                under,
                {
                  x: Math.sign(s.f || 1) * 380 * s.strike.power,
                  r: Math.sign(s.f || 1) * 6 * s.strike.power,
                },
                1,
              );
          }
        }
      }

      function setAct(a: Act) {
        if (s.act !== a) {
          s.act = a;
          s.actT = 0;
        }
      }
      function jump(height: number, vx: number) {
        s.mode = "fall";
        s.vy = -Math.sqrt(2 * GRAVITY * Math.max(0.2 * H, height));
        s.vx = vx;
        s.strike = null;
        s.squash.kick(-2);
        dust(s.x, s.y, 0.5);
      }
    };

    // ── drawing ──
    const draw = () => {
      const sy = window.scrollY;
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.clearRect(box.x0, box.y0, box.x1 - box.x0, box.y1 - box.y0);
      ctx.setTransform(dpr, 0, 0, dpr, 0, -sy * dpr);
      const j = s.j;
      let x0 = Infinity;
      let y0 = Infinity;
      let x1 = -Infinity;
      let y1 = -Infinity;
      const grow = (x: number, y: number, r: number) => {
        x0 = Math.min(x0, x - r);
        y0 = Math.min(y0, y - r);
        x1 = Math.max(x1, x + r);
        y1 = Math.max(y1, y + r);
      };
      if (j) {
        const d = s.d;
        // ground shadow
        if (s.mode !== "ragdoll") {
          const b: Bounds = {
            left: 0,
            right: window.innerWidth,
            ceil: sy + 70,
            floor: sy + window.innerHeight - 8,
          };
          const sup =
            s.mode === "ground" || s.mode === "getup" ? s.y : supportUnder(s.x, s.y, b).top;
          const air = clamp01((sup - Math.max(j.footA.y, j.footB.y)) / (2 * s.H));
          ctx.globalAlpha = 0.18 * (1 - 0.7 * air);
          ctx.fillStyle = ink;
          ctx.beginPath();
          ctx.ellipse(
            (j.footA.x + j.footB.x) / 2,
            sup,
            0.26 * s.H * (1 - 0.5 * air),
            0.035 * s.H,
            0,
            0,
            Math.PI * 2,
          );
          ctx.fill();
          grow((j.footA.x + j.footB.x) / 2, sup, 0.3 * s.H);
        }
        ctx.lineCap = "round";
        ctx.lineJoin = "round";
        const line = (a: Vec, c: Vec, w: number) => {
          ctx.lineWidth = w;
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(c.x, c.y);
          ctx.stroke();
          grow(a.x, a.y, w);
          grow(c.x, c.y, w);
        };
        const body = (colour: string, extra: number, alpha: number) => {
          ctx.strokeStyle = colour;
          ctx.fillStyle = colour;
          ctx.globalAlpha = alpha;
          line(j.pelvis, j.kneeB, d.wThigh + extra);
          line(j.kneeB, j.footB, d.wShin + extra);
          line(j.shoulder, j.elbowB, d.wUpper + extra);
          line(j.elbowB, j.handB, d.wFore + extra);
          line(j.pelvis, j.chest, d.wTorso + extra);
          line(j.pelvis, j.kneeA, d.wThigh + extra);
          line(j.kneeA, j.footA, d.wShin + extra);
          line(j.shoulder, j.elbowA, d.wUpper + extra);
          line(j.elbowA, j.handA, d.wFore + extra);
          ctx.beginPath();
          ctx.arc(j.head.x, j.head.y, d.head + extra / 2, 0, Math.PI * 2);
          ctx.fill();
          grow(j.head.x, j.head.y, d.head + extra);
        };
        // a page-coloured outline first, so he reads on any background, then the body
        body(halo, 3, 0.85);
        body(ink, 0, 1);
      }
      // particles
      for (const q of s.ps) {
        const k = 1 - q.age / q.life;
        if (q.kind === "spark") {
          const sp = Math.hypot(q.vx, q.vy) || 1;
          const len = q.size * (0.4 + 0.6 * k);
          ctx.globalAlpha = k;
          ctx.strokeStyle = accent;
          ctx.lineWidth = 2.6;
          ctx.beginPath();
          ctx.moveTo(q.x, q.y);
          ctx.lineTo(q.x - (q.vx / sp) * len, q.y - (q.vy / sp) * len);
          ctx.stroke();
          grow(q.x, q.y, len + 4);
        } else if (q.kind === "dust") {
          ctx.globalAlpha = 0.3 * k;
          ctx.fillStyle = ink;
          ctx.beginPath();
          const r = q.size * (1 + 1.4 * (1 - k));
          ctx.arc(q.x, q.y, r, 0, Math.PI * 2);
          ctx.fill();
          grow(q.x, q.y, r + 2);
        } else {
          ctx.globalAlpha = 0.9 * k;
          ctx.strokeStyle = accent;
          ctx.lineWidth = 3 * k + 0.5;
          const r = q.size * (0.4 + 0.9 * (1 - k));
          ctx.beginPath();
          ctx.arc(q.x, q.y, r, 0, Math.PI * 2);
          ctx.stroke();
          grow(q.x, q.y, r + 4);
        }
      }
      ctx.globalAlpha = 1;
      // remember what was painted (device pixels) so the next frame clears only that
      if (x0 === Infinity) box = { x0: 0, y0: 0, x1: 0, y1: 0 };
      else
        box = {
          x0: Math.max(0, Math.floor((x0 - 4) * dpr)),
          y0: Math.max(0, Math.floor((y0 - sy - 4) * dpr)),
          x1: Math.min(cv.width, Math.ceil((x1 + 4) * dpr)),
          y1: Math.min(cv.height, Math.ceil((y1 - sy + 4) * dpr)),
        };
      // scrolling moves everything: clear it all next frame
      if (sy !== lastSy) {
        box = { x0: 0, y0: 0, x1: cv.width, y1: cv.height };
        lastSy = sy;
      }
    };
    let lastSy = window.scrollY;

    s.plats = scan();
    raf = requestAnimationFrame(frame);
    return () => {
      cancelAnimationFrame(raf);
      themeObs.disconnect();
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerdown", onDown, { capture: true });
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("pointercancel", onUp);
      document.removeEventListener("pointerleave", onLeave);
      window.removeEventListener("touchstart", onTouch);
      window.removeEventListener("resize", fit);
      document.documentElement.style.cursor = "";
    };
  }, []);

  return (
    <canvas
      ref={canvas}
      aria-hidden
      className="pointer-events-none fixed inset-0 z-40 h-screen w-screen"
      style={{ width: "100vw", height: "100vh" }}
    />
  );
}

function useMotionAllowed() {
  return useSyncExternalStore(
    (cb) => {
      const m = window.matchMedia("(prefers-reduced-motion: reduce)");
      m.addEventListener("change", cb);
      return () => m.removeEventListener("change", cb);
    },
    () => !window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    () => false,
  );
}

/** The roaming fighter, unless the layer is off or the visitor asked for less motion. */
export function Roamer() {
  const allowed = useMotionAllowed();
  return FIGURES_ON && allowed ? <RoamerLayer /> : null;
}
