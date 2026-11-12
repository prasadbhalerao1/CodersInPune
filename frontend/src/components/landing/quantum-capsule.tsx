"use client";

import React, { useEffect, useRef } from "react";

export function QuantumCapsule() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animationFrameId = 0;
    let t = 0;

    // High-DPI canvas setup
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const width = 380;
    const height = 88;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);

    // Particle system for quantum energy stream
    interface Particle {
      x: number;
      y: number;
      vx: number;
      size: number;
      orbitA: number;
      orbitSpeed: number;
      orbitPhase: number;
      color: string;
      glowColor: string;
    }

    const particles: Particle[] = [];
    const NUM_PARTICLES = 180;

    const palette = [
      { fill: "#C4FF00", glow: "rgba(196, 255, 0, 0.95)" }, // Neon lime
      { fill: "#D2FF00", glow: "rgba(210, 255, 0, 1.0)" }, // Chartreuse
      { fill: "#FFE600", glow: "rgba(255, 230, 0, 0.9)" }, // Electric gold
      { fill: "#FFA500", glow: "rgba(255, 165, 0, 0.85)" }, // Bright amber
      { fill: "#FF6600", glow: "rgba(255, 102, 0, 0.75)" }, // Warm orange
      { fill: "#FFFFFF", glow: "rgba(255, 255, 255, 1.0)" }, // Core spark
    ];

    for (let i = 0; i < NUM_PARTICLES; i++) {
      const p = palette[Math.floor(Math.random() * palette.length)];
      particles.push({
        x: Math.random() * width,
        y: height / 2,
        vx: 0.5 + Math.random() * 1.0,
        size: Math.random() < 0.15 ? 2.8 + Math.random() * 1.5 : 0.8 + Math.random() * 1.6,
        orbitA: 5 + Math.random() * 26,
        orbitSpeed: 0.025 + Math.random() * 0.05,
        orbitPhase: Math.random() * Math.PI * 2,
        color: p.fill,
        glowColor: p.glow,
      });
    }

    const render = () => {
      t += 0.028;
      ctx.clearRect(0, 0, width, height);

      // 1. Ambient Volumetric Fluid Gradient
      const ambientGrad = ctx.createRadialGradient(
        width * 0.5,
        height * 0.5,
        4,
        width * 0.5,
        height * 0.5,
        width * 0.5,
      );
      ambientGrad.addColorStop(0, "rgba(210, 255, 0, 0.3)");
      ambientGrad.addColorStop(0.35, "rgba(255, 160, 0, 0.2)");
      ambientGrad.addColorStop(0.7, "rgba(255, 90, 0, 0.08)");
      ambientGrad.addColorStop(1, "rgba(0, 0, 0, 0)");
      ctx.fillStyle = ambientGrad;
      ctx.fillRect(0, 0, width, height);

      // High-energy additive blending
      ctx.globalCompositeOperation = "lighter";

      // 2. Continuous Amber/Orange Filament (Pym particle core)
      ctx.beginPath();
      for (let x = 0; x <= width; x += 4) {
        const y1 = Math.sin(x * 0.022 + t * 1.6) * 19;
        const y2 = Math.cos(x * 0.04 - t * 1.1) * 8;
        const y = height / 2 + y1 + y2;
        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.strokeStyle = "rgba(255, 130, 0, 0.45)";
      ctx.lineWidth = 15;
      ctx.filter = "blur(7px)";
      ctx.stroke();

      ctx.beginPath();
      for (let x = 0; x <= width; x += 4) {
        const y1 = Math.sin(x * 0.022 + t * 1.6) * 19;
        const y2 = Math.cos(x * 0.04 - t * 1.1) * 8;
        const y = height / 2 + y1 + y2;
        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.strokeStyle = "rgba(255, 205, 30, 0.8)";
      ctx.lineWidth = 5.5;
      ctx.filter = "blur(2px)";
      ctx.stroke();

      // 3. Continuous Electric Lime / Chartreuse Helix
      ctx.beginPath();
      for (let x = 0; x <= width; x += 4) {
        const y1 = Math.sin(x * 0.024 - t * 1.9 + Math.PI) * 21;
        const y2 = Math.sin(x * 0.042 + t * 1.3) * 7;
        const y = height / 2 + y1 + y2;
        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.strokeStyle = "rgba(196, 255, 0, 0.6)";
      ctx.lineWidth = 16;
      ctx.filter = "blur(8px)";
      ctx.stroke();

      ctx.beginPath();
      for (let x = 0; x <= width; x += 4) {
        const y1 = Math.sin(x * 0.024 - t * 1.9 + Math.PI) * 21;
        const y2 = Math.sin(x * 0.042 + t * 1.3) * 7;
        const y = height / 2 + y1 + y2;
        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.strokeStyle = "rgba(225, 255, 70, 0.95)";
      ctx.lineWidth = 4.5;
      ctx.filter = "blur(1.5px)";
      ctx.stroke();

      // 4. White-Hot Intense Reaction Filaments
      ctx.beginPath();
      for (let x = 0; x <= width; x += 5) {
        const yL = height / 2 + Math.sin(x * 0.024 - t * 1.9 + Math.PI) * 21;
        const yG = height / 2 + Math.sin(x * 0.022 + t * 1.6) * 19;
        const y = (yL + yG) * 0.5;
        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.strokeStyle = "rgba(255, 255, 255, 0.95)";
      ctx.lineWidth = 1.8;
      ctx.filter = "none";
      ctx.stroke();

      // 5. Kinetic Particles & Sparkling Dust
      for (const p of particles) {
        p.x += p.vx;
        if (p.x > width + 10) {
          p.x = -10;
        }

        p.orbitPhase += p.orbitSpeed;
        const currentY =
          height / 2 + Math.sin(p.orbitPhase) * (p.orbitA * Math.sin(p.x * 0.018 + t));
        p.y = currentY;

        ctx.fillStyle = p.glowColor;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size * 1.8, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = p.color;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size * 0.85, 0, Math.PI * 2);
        ctx.fill();
      }

      ctx.globalCompositeOperation = "source-over";
      animationFrameId = requestAnimationFrame(render);
    };

    // Reduced motion: paint one still frame instead of animating.
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      render();
      cancelAnimationFrame(animationFrameId);
      return;
    }

    render();

    return () => {
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  return (
    <div
      aria-hidden
      className="pointer-events-auto relative inline-flex items-center justify-center select-none"
    >
      {/* Volumetric Radial Ambient Glow onto the red background */}
      <div
        aria-hidden
        className="pointer-events-none absolute -inset-24 rounded-full bg-gradient-to-r from-[#C4FF00]/22 via-[#FF9900]/16 to-[#7E1520]/28 opacity-90 blur-3xl"
      />

      {/* 
        The Physical Capsule Assembly
        Oriented at -40° angle (lower-left to upper-right)
      */}
      <div
        className="relative flex items-center"
        style={{
          transform: "rotate(-40deg)",
          transformOrigin: "center center",
        }}
      >
        {/* =========================================================================
            BOTTOM KNURLED TITANIUM BASE CAP (Lower-Left)
            ========================================================================= */}
        <div className="relative z-20 -mr-[2px] flex items-center">
          {/* Stepped concave end socket */}
          <div className="h-16 w-3.5 rounded-l-full border-y border-l border-white/20 bg-gradient-to-r from-[#181C24] via-[#373E4D] to-[#252B36] shadow-[-6px_0_16px_rgba(0,0,0,0.9)]" />

          {/* Main knurled titanium grip body */}
          <div className="relative h-[90px] w-14 overflow-hidden rounded-xs border-y border-white/35 bg-gradient-to-b from-[#717886] via-[#3E4554] via-[#E2E8F0] via-28% via-62% to-[#0F141C] shadow-[0_6px_24px_rgba(0,0,0,0.9)]">
            {/* Knurled diamond cross-hatch texture */}
            <div
              className="pointer-events-none absolute inset-0 opacity-45 mix-blend-overlay"
              style={{
                backgroundImage: `
                  repeating-linear-gradient(45deg, #000 0, #000 1.5px, transparent 1.5px, transparent 3.5px),
                  repeating-linear-gradient(-45deg, #fff 0, #fff 1.5px, transparent 1.5px, transparent 3.5px)
                `,
                backgroundSize: "4px 4px",
              }}
            />
            {/* Specular longitudinal reflection highlights */}
            <div className="absolute inset-x-0 top-1 h-[2px] bg-white/80 blur-[0.4px]" />
            <div className="absolute inset-x-0 top-3.5 h-[1px] bg-white/45" />
            <div className="absolute inset-x-0 bottom-2 h-[1.5px] bg-black/70" />
          </div>

          {/* Stepped polished titanium collar ring */}
          <div className="relative h-[84px] w-4 border-y border-r border-black/90 bg-gradient-to-b from-[#9CA3AF] via-[#4B5563] via-[#F3F4F6] via-25% via-65% to-[#1F2937] shadow-[inset_1px_0_2px_rgba(255,255,255,0.4)]">
            <div className="absolute inset-y-0 right-0 w-[1px] bg-black/90" />
          </div>

          {/* Precision rubber compression seal */}
          <div className="h-[80px] w-1.5 border-y border-black bg-[#090C10]" />
        </div>

        {/* =========================================================================
            BOROSILICATE QUARTZ GLASS CYLINDER + KINETIC PARTICLES
            ========================================================================= */}
        <div className="relative z-10 h-[80px] w-[380px] overflow-hidden border-y border-white/25 bg-[#02050C]/55 shadow-[inset_0_2px_8px_rgba(255,255,255,0.3),inset_0_-2px_8px_rgba(0,0,0,0.85),0_12px_32px_rgba(0,0,0,0.85)] backdrop-blur-[2px]">
          {/* Glass Inner Reflection Gradient */}
          <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-white/[0.09] via-transparent to-black/45" />

          {/* Laser-Etched Measurement Scale (Medical / Scientific Graduations) */}
          <div className="pointer-events-none absolute inset-x-0 top-0 z-20 flex h-4 items-start justify-between px-6 opacity-65">
            {[0, 10, 20, 30, 40, 50, 60, 70, 80, 90].map((val, i) => (
              <div key={i} className="flex flex-col items-center">
                <span className={`w-[1px] bg-white/85 ${i % 2 === 0 ? "h-2.5" : "h-1.5"}`} />
                {i % 2 === 0 && (
                  <span className="mt-0.5 font-mono text-[6.5px] tracking-tighter text-zinc-300">
                    {val}
                  </span>
                )}
              </div>
            ))}
          </div>

          {/* Interactive HTML5 Particle Vortex Canvas */}
          <canvas
            ref={canvasRef}
            className="pointer-events-none absolute inset-0 z-10 h-full w-full"
            style={{ width: "380px", height: "80px" }}
          />

          {/* Front Borosilicate Glass Specular Beams */}
          <div className="pointer-events-none absolute inset-x-0 top-0 z-20 h-[2.5px] bg-gradient-to-r from-white/30 via-white/85 via-white/95 via-30% via-70% to-white/30 shadow-[0_0_8px_rgba(255,255,255,0.9)]" />
          <div className="pointer-events-none absolute inset-x-0 top-2 z-20 h-[1px] bg-gradient-to-r from-transparent via-white/50 via-40% to-transparent" />
          <div className="pointer-events-none absolute inset-x-0 bottom-0 z-20 h-[1.5px] bg-gradient-to-r from-white/10 via-white/35 to-white/10" />
          <div className="pointer-events-none absolute inset-x-0 bottom-2 z-20 h-[1px] bg-black/50" />
        </div>

        {/* =========================================================================
            TOP KNURLED TITANIUM HEAD CAP & LATCH BRACKET (Upper-Right)
            ========================================================================= */}
        <div className="relative z-20 -ml-[2px] flex items-center">
          {/* Precision rubber compression seal */}
          <div className="h-[80px] w-1.5 border-y border-black bg-[#090C10]" />

          {/* Stepped polished titanium collar ring */}
          <div className="relative h-[84px] w-4 border-y border-l border-black/90 bg-gradient-to-b from-[#9CA3AF] via-[#4B5563] via-[#F3F4F6] via-25% via-65% to-[#1F2937] shadow-[inset_-1px_0_2px_rgba(255,255,255,0.4)]">
            <div className="absolute inset-y-0 left-0 w-[1px] bg-black/90" />
          </div>

          {/* Main knurled head cylinder with quick-release side clamp */}
          <div className="relative h-[90px] w-16 overflow-hidden rounded-xs border-y border-white/35 bg-gradient-to-b from-[#717886] via-[#3E4554] via-[#E2E8F0] via-28% via-62% to-[#0F141C] shadow-[0_6px_24px_rgba(0,0,0,0.9)]">
            {/* Knurled diamond cross-hatch texture */}
            <div
              className="pointer-events-none absolute inset-0 opacity-45 mix-blend-overlay"
              style={{
                backgroundImage: `
                  repeating-linear-gradient(45deg, #000 0, #000 1.5px, transparent 1.5px, transparent 3.5px),
                  repeating-linear-gradient(-45deg, #fff 0, #fff 1.5px, transparent 1.5px, transparent 3.5px)
                `,
                backgroundSize: "4px 4px",
              }}
            />
            {/* Specular longitudinal reflection highlights */}
            <div className="absolute inset-x-0 top-1 h-[2px] bg-white/80 blur-[0.4px]" />
            <div className="absolute inset-x-0 top-3.5 h-[1px] bg-white/45" />
            <div className="absolute inset-x-0 bottom-2 h-[1.5px] bg-black/70" />

            {/* Quick-Release Mechanical Latch Bracket */}
            <div className="absolute -top-1 left-3 flex h-3.5 w-5.5 items-center justify-center rounded-sm border border-black bg-gradient-to-b from-[#F3F4F6] to-[#4B5563] shadow-md">
              <span className="h-1.5 w-1.5 rounded-full bg-[#111827] shadow-[inset_0_0.5px_1px_rgba(255,255,255,0.4)]" />
            </div>
          </div>

          {/* Stepped secondary titanium bezel ring */}
          <div className="h-[80px] w-3 border-y border-white/25 bg-gradient-to-b from-[#9CA3AF] via-[#E5E7EB] to-[#1F2937]" />

          {/* Terminal Domed Machined Socket Ring */}
          <div className="h-16 w-3.5 rounded-r-full border-y border-r border-white/20 bg-gradient-to-r from-[#252B36] via-[#373E4D] to-[#181C24] shadow-[6px_0_16px_rgba(0,0,0,0.9)]" />
        </div>
      </div>
    </div>
  );
}
