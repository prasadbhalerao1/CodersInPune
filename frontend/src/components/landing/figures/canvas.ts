/**
 * Drawing a figure (and its props) on a 2D canvas, in the same style as the SVG figures: one
 * heavy line weight per segment with round ends, a solid head, the far limbs behind, and a
 * page-coloured outline underneath so the figure reads on any background.
 */

import type { Dims, Joints, Vec } from "./rig";

export type Ink = { ink: string; accent: string; page: string };

export function readInk(): Ink {
  const cs = getComputedStyle(document.documentElement);
  return {
    ink: cs.getPropertyValue("--strong").trim() || "#0b1230",
    accent: cs.getPropertyValue("--ac").trim() || "#2540c8",
    page: cs.getPropertyValue("--page").trim() || "#f3f5ff",
  };
}

const line = (ctx: CanvasRenderingContext2D, a: Vec, b: Vec, w: number) => {
  ctx.lineWidth = w;
  ctx.beginPath();
  ctx.moveTo(a.x, a.y);
  ctx.lineTo(b.x, b.y);
  ctx.stroke();
};

export function drawBody(
  ctx: CanvasRenderingContext2D,
  j: Joints,
  d: Dims,
  c: Ink,
  o: { alpha?: number; thumb?: boolean } = {},
) {
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  const pass = (colour: string, extra: number, alpha: number) => {
    ctx.strokeStyle = colour;
    ctx.fillStyle = colour;
    ctx.globalAlpha = alpha;
    line(ctx, j.pelvis, j.kneeB, d.wThigh + extra);
    line(ctx, j.kneeB, j.footB, d.wShin + extra);
    line(ctx, j.shoulder, j.elbowB, d.wUpper + extra);
    line(ctx, j.elbowB, j.handB, d.wFore + extra);
    line(ctx, j.pelvis, j.chest, d.wTorso + extra);
    line(ctx, j.pelvis, j.kneeA, d.wThigh + extra);
    line(ctx, j.kneeA, j.footA, d.wShin + extra);
    line(ctx, j.shoulder, j.elbowA, d.wUpper + extra);
    line(ctx, j.elbowA, j.handA, d.wFore + extra);
    if (o.thumb)
      line(ctx, j.handA, { x: j.handA.x, y: j.handA.y - 0.075 * d.H }, d.wFore * 0.7 + extra);
    ctx.beginPath();
    ctx.arc(j.head.x, j.head.y, d.head + extra / 2, 0, Math.PI * 2);
    ctx.fill();
  };
  const a = o.alpha ?? 1;
  pass(c.page, 3, 0.85 * a);
  pass(c.ink, 0, a);
  ctx.globalAlpha = 1;
}

export function drawShadow(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  d: Dims,
  air: number,
  c: Ink,
  alpha = 1,
) {
  ctx.globalAlpha = 0.18 * (1 - 0.7 * air) * alpha;
  ctx.fillStyle = c.ink;
  ctx.beginPath();
  ctx.ellipse(x, y, 0.26 * d.H * (1 - 0.5 * air), 0.035 * d.H, 0, 0, Math.PI * 2);
  ctx.fill();
  ctx.globalAlpha = 1;
}
