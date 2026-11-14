"use client";

import { useEffect, useRef } from "react";

import {
  CHEER,
  PRESENT,
  READ,
  STAND,
  THINK,
  approach,
  dims,
  gait,
  mix,
  nod,
  smooth,
  solve,
  stride,
  vlerp,
  wave,
  type Joints,
  type Pose,
  type Reach,
  type Vec,
} from "./rig";
import {
  FigureGlyph,
  drawBaton,
  drawFigure,
  drawRect,
  useStage,
  figure,
  FIGURES_ON,
} from "./stage";

type Actor = { x: number; f: number; ph: number; pose: Pose };
type Cue = { x: number; face: 1 | -1; pose: Pose; reach?: boolean };
type Sim = {
  step: number;
  ts: number;
  a: Actor;
  d: Actor;
  baton: Vec | null;
  batonOp: number;
  docOp: number;
};

/**
 * Arjun (leaving) and Dev (taking over) act out the walkthrough's current step on top of its
 * card: Arjun waves and walks off; he reads the evidence; he shows it to Dev, who thinks it
 * over; the baton changes hands; Dev holds it up. They walk between marks and turn on the spot.
 */
function WalkthroughFiguresScene({ step }: { step: number }) {
  const svg = useRef<SVGSVGElement>(null);
  const baton = useRef<SVGLineElement>(null);
  const doc = useRef<SVGRectElement>(null);
  const sim = useRef<Sim | null>(null);

  const kick = useStage(svg, (dt, w, h, still) => {
    const H = w < 640 ? 42 : 52;
    const dm = dims(H);
    const ground = h - dm.stroke / 2;
    const s = (sim.current ??= {
      step: -1,
      ts: 0,
      a: { x: w * 0.3, f: 1, ph: 0, pose: STAND },
      d: { x: w * 0.64, f: -1, ph: 0, pose: STAND },
      baton: null,
      batonOp: 0,
      docOp: 0,
    });
    if (s.step !== step) {
      s.step = step;
      s.ts = 0;
    }
    s.ts += dt;
    const ts = still ? 2 : s.ts;
    const mid = w * 0.47;

    // where each of them should be, and doing what, at this moment of the step
    let ca: Cue;
    let cd: Cue = { x: w * 0.64, face: -1, pose: { ...STAND, head: 0.08 } };
    let holder: "a-far" | "a-near" | "d-near" | null = null;
    let showDoc = false;
    if (step === 0) {
      ca =
        ts < 1.4
          ? { x: w * 0.3, face: 1, pose: wave(ts) }
          : { x: w * 0.1, face: -1, pose: { ...STAND, head: -0.08 } };
      holder = "a-far";
    } else if (step === 1) {
      ca = { x: w * 0.3, face: 1, pose: READ };
      showDoc = true;
    } else if (step === 2) {
      ca = { x: w * 0.36, face: 1, pose: PRESENT };
      cd = { x: w * 0.6, face: -1, pose: THINK };
      showDoc = true;
    } else if (step === 3) {
      ca = { x: mid - 0.22 * H, face: 1, pose: STAND, reach: true };
      cd = { x: mid + 0.22 * H, face: -1, pose: STAND, reach: true };
      holder = ts < 1.3 ? "a-near" : "d-near";
    } else {
      ca = { x: mid - 0.7 * H, face: 1, pose: nod(ts) };
      cd = { x: mid + 0.22 * H, face: -1, pose: CHEER };
      holder = "d-near";
    }

    const move = (act: Actor, cue: Cue) => {
      if (still) {
        act.x = cue.x;
        act.f = cue.face;
        act.pose = cue.pose;
        return;
      }
      const gap = cue.x - act.x;
      const moving = Math.abs(gap) > 0.5;
      if (moving) {
        const dx = Math.sign(gap) * Math.min(Math.abs(gap), 1.25 * H * dt);
        act.x += dx;
        act.ph += (2 * Math.PI * Math.abs(dx)) / stride(0, H);
      }
      // turning passes through edge-on, which reads as a turn rather than a flip
      act.f += ((moving ? Math.sign(gap) : cue.face) - act.f) * approach(dt, 10);
      act.pose = mix(act.pose, moving ? gait(act.ph, 0) : cue.pose, approach(dt, moving ? 16 : 7));
    };
    move(s.a, ca);
    move(s.d, cd);

    // in the hand-over both near hands meet between them, chest-high
    const reachW = step === 3 ? smooth((ts - 0.35) / 0.4) * (1 - smooth((ts - 2.3) / 0.4)) : 0;
    const pre = (act: Actor) => solve(act.pose, dm, act.x, ground, act.f);
    const ja0 = pre(s.a);
    const jd0 = pre(s.d);
    const target = {
      x: (ja0.chest.x + jd0.chest.x) / 2,
      y: (ja0.chest.y + jd0.chest.y) / 2 + 0.22 * H,
    };
    const reach: Reach | undefined = reachW > 0 ? { target, w: reachW } : undefined;
    const ja: Joints =
      ca.reach && reach ? solve(s.a.pose, dm, s.a.x, ground, s.a.f, { reachA: reach }) : ja0;
    const jd: Joints =
      cd.reach && reach ? solve(s.d.pose, dm, s.d.x, ground, s.d.f, { reachA: reach }) : jd0;
    drawFigure(figure(svg.current, "a"), ja, dm, { groundY: ground });
    drawFigure(figure(svg.current, "d"), jd, dm, { groundY: ground });

    // the baton travels between hands rather than jumping
    const grip =
      holder === "a-far"
        ? { hand: ja.handB, elbow: ja.elbowB }
        : holder === "a-near"
          ? { hand: ja.handA, elbow: ja.elbowA }
          : holder === "d-near"
            ? { hand: jd.handA, elbow: jd.elbowA }
            : null;
    s.batonOp += ((grip ? 1 : 0) - s.batonOp) * (still ? 1 : approach(dt, 8));
    if (grip) s.baton = s.baton && !still ? vlerp(s.baton, grip.hand, approach(dt, 14)) : grip.hand;
    if (s.baton) drawBaton(baton.current, s.baton, grip?.elbow ?? ja.elbowB, dm, s.batonOp);

    // the evidence: a sheet held in both hands, then held out
    s.docOp += ((showDoc ? 1 : 0) - s.docOp) * (still ? 1 : approach(dt, 8));
    const sheet =
      step === 2
        ? { x: ja.handA.x + s.a.f * 0.06 * H, y: ja.handA.y - 0.06 * H }
        : vlerp(ja.handA, ja.handB, 0.5);
    drawRect(
      doc.current,
      { x: sheet.x, y: sheet.y - 0.05 * H },
      0.17 * H,
      0.22 * H,
      step === 2 ? 0.12 : -0.08,
      s.docOp,
      dm.stroke * 0.6,
    );
  });

  useEffect(() => kick(), [kick, step]);

  return (
    <div aria-hidden className="relative h-16">
      <svg
        ref={svg}
        className="pointer-events-none absolute inset-0 h-full w-full overflow-visible"
      >
        <FigureGlyph name="a" />
        <FigureGlyph name="d" />
        <rect ref={doc} rx={1.5} className="fig-doc" />
        <line ref={baton} className="fig-baton" />
      </svg>
    </div>
  );
}

export function WalkthroughFigures(props: Parameters<typeof WalkthroughFiguresScene>[0]) {
  return FIGURES_ON ? <WalkthroughFiguresScene {...props} /> : null;
}
