"use client";

/**
 * Sparks and dust. Sparks are short accent streaks thrown out of a contact point (a slam, a
 * catch, a hand-off); dust is soft ink puffs kicked out along the ground (a landing, a skid, a
 * stamp). A fixed pool per stage, updated in place, deterministic (no Math.random: a seeded
 * generator), so a replay looks the same.
 */

type P = {
  kind: "spark" | "dust";
  x: number;
  y: number;
  vx: number;
  vy: number;
  life: number;
  age: number;
  size: number;
};
type Pool = { ps: P[]; seed: number; sparks: SVGLineElement[]; dust: SVGCircleElement[] };

const SPARKS = 18;
const DUST = 14;
const pools = new WeakMap<SVGSVGElement, Pool>();

function pool(svg: SVGSVGElement): Pool | null {
  const hit = pools.get(svg);
  if (hit && hit.sparks[0]?.isConnected) return hit;
  const sparks = [...svg.querySelectorAll<SVGLineElement>("[data-fx=spark]")];
  const dust = [...svg.querySelectorAll<SVGCircleElement>("[data-fx=dust]")];
  if (!sparks.length || !dust.length) return null;
  const p = { ps: [], seed: 7, sparks, dust };
  pools.set(svg, p);
  return p;
}

const rand = (p: Pool) => {
  // xorshift: cheap, seeded
  let x = p.seed;
  x ^= x << 13;
  x ^= x >>> 17;
  x ^= x << 5;
  p.seed = x >>> 0;
  return (p.seed % 10000) / 10000;
};

/**
 * Throw sparks out of (x, y) around `angle` (radians, screen space, 0 = right, -π/2 = up)
 * within `spread`. `power` scales count and speed (1 = a solid hit).
 */
export function sparks(
  svg: SVGSVGElement | null,
  x: number,
  y: number,
  angle: number,
  spread: number,
  power = 1,
) {
  const p = svg && pool(svg);
  if (!p) return;
  const n = Math.round(6 + 8 * Math.min(1.5, power));
  for (let i = 0; i < n; i++) {
    const a = angle + (rand(p) - 0.5) * spread;
    const v = (260 + 420 * rand(p)) * (0.6 + 0.5 * power);
    p.ps.push({
      kind: "spark",
      x,
      y,
      vx: Math.cos(a) * v,
      vy: Math.sin(a) * v,
      life: 0.22 + 0.18 * rand(p),
      age: 0,
      size: 6 + 7 * rand(p),
    });
  }
}

/** Kick dust out along the ground from (x, y): `dir` -1 left, 1 right, 0 both ways. */
export function dust(svg: SVGSVGElement | null, x: number, y: number, dir: number, power = 1) {
  const p = svg && pool(svg);
  if (!p) return;
  const n = Math.round(3 + 5 * Math.min(1.5, power));
  for (let i = 0; i < n; i++) {
    const side = dir === 0 ? (i % 2 ? 1 : -1) : dir;
    const v = (40 + 110 * rand(p)) * (0.6 + 0.6 * power);
    p.ps.push({
      kind: "dust",
      x: x + side * 4 * rand(p),
      y,
      vx: side * v,
      vy: -(20 + 60 * rand(p)),
      life: 0.45 + 0.35 * rand(p),
      age: 0,
      size: 2.5 + 4 * rand(p) * power,
    });
  }
}

/** Advance and draw the stage's particles. Call once per frame. */
export function stepParticles(svg: SVGSVGElement | null, dt: number) {
  const p = svg && pool(svg);
  if (!p) return;
  for (const q of p.ps) {
    q.age += dt;
    if (q.kind === "spark") {
      q.vx *= Math.exp(-dt * 7);
      q.vy = q.vy * Math.exp(-dt * 7) + 900 * dt;
    } else {
      q.vx *= Math.exp(-dt * 4);
      q.vy *= Math.exp(-dt * 3);
    }
    q.x += q.vx * dt;
    q.y += q.vy * dt;
  }
  p.ps = p.ps.filter((q) => q.age < q.life);
  let si = 0;
  let di = 0;
  for (const q of p.ps) {
    const k = 1 - q.age / q.life;
    if (q.kind === "spark" && si < p.sparks.length) {
      const el = p.sparks[si++]!;
      const sp = Math.hypot(q.vx, q.vy) || 1;
      const len = q.size * (0.4 + 0.6 * k);
      el.setAttribute("x1", q.x.toFixed(1));
      el.setAttribute("y1", q.y.toFixed(1));
      el.setAttribute("x2", (q.x - (q.vx / sp) * len).toFixed(1));
      el.setAttribute("y2", (q.y - (q.vy / sp) * len).toFixed(1));
      el.style.opacity = k.toFixed(2);
    } else if (q.kind === "dust" && di < p.dust.length) {
      const el = p.dust[di++]!;
      el.setAttribute("cx", q.x.toFixed(1));
      el.setAttribute("cy", q.y.toFixed(1));
      el.setAttribute("r", (q.size * (1 + 1.4 * (1 - k))).toFixed(1));
      el.style.opacity = (0.32 * k).toFixed(2);
    }
  }
  for (; si < p.sparks.length; si++) p.sparks[si]!.style.opacity = "0";
  for (; di < p.dust.length; di++) p.dust[di]!.style.opacity = "0";
}

/** The pool's nodes. Put one inside every stage that throws sparks or dust. */
export function Particles() {
  return (
    <g aria-hidden>
      {Array.from({ length: DUST }, (_, i) => (
        <circle key={`d${i}`} data-fx="dust" className="fx-dust" style={{ opacity: 0 }} />
      ))}
      {Array.from({ length: SPARKS }, (_, i) => (
        <line key={`s${i}`} data-fx="spark" className="fx-spark" style={{ opacity: 0 }} />
      ))}
    </g>
  );
}
