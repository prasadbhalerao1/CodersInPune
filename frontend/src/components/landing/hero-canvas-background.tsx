"use client";

import React from "react";

const SLASH = "polygon(56% 0%, 100% 0%, 100% 32%, 64% 100%, 25% 100%)";

/** Cobalt slash, a lime bloom, an engineering grid and film grain. The page-level petals show through. */
export function HeroCanvasBackground() {
  return (
    <div
      aria-hidden
      className="pointer-events-none absolute inset-0 z-0 overflow-hidden select-none"
    >
      <div
        className="absolute inset-0"
        style={{
          clipPath: SLASH,
          background: "linear-gradient(135deg, #3A58FF 0%, #1D32C2 32%, #11207F 68%, #08104A 100%)",
          opacity: 0.9,
        }}
      />
      <div
        className="absolute inset-0 opacity-40 mix-blend-overlay"
        style={{
          clipPath: SLASH,
          background:
            "linear-gradient(90deg, rgba(255,255,255,0.2) 0%, transparent 40%, rgba(0,0,0,0.4) 100%)",
        }}
      />
      <div
        className="absolute inset-0 opacity-70"
        style={{
          clipPath: SLASH,
          background:
            "linear-gradient(to bottom right, rgba(160,185,255,0.45), transparent 18%, transparent 82%, rgba(160,185,255,0.25))",
          maskImage: "linear-gradient(to right, #000, transparent 12%, transparent 88%, #000)",
        }}
      />
      <div className="absolute top-[18%] right-[8%] h-[70%] w-[46%] rounded-full bg-[radial-gradient(ellipse_at_center,rgba(184,255,60,0.16),rgba(60,100,255,0.1)_40%,transparent_70%)] blur-2xl" />
      <div
        className="absolute inset-0 opacity-[0.06]"
        style={{
          backgroundImage:
            "linear-gradient(rgba(255,255,255,1) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,1) 1px, transparent 1px)",
          backgroundSize: "64px 64px",
          maskImage: "radial-gradient(ellipse at 70% 45%, #000 0%, transparent 70%)",
        }}
      />
      <svg className="absolute inset-0 h-full w-full opacity-[0.1] mix-blend-overlay">
        <filter id="hero-grain">
          <feTurbulence
            type="fractalNoise"
            baseFrequency="0.9"
            numOctaves="2"
            stitchTiles="stitch"
          />
          <feColorMatrix values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 0.9 0" />
        </filter>
        <rect width="100%" height="100%" filter="url(#hero-grain)" />
      </svg>
    </div>
  );
}
