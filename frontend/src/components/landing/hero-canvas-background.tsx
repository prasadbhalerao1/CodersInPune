"use client";

import React from "react";

export function HeroCanvasBackground() {
  return (
    <div
      aria-hidden
      className="pointer-events-none absolute inset-0 z-0 overflow-hidden bg-[#090D18] select-none"
    >
      {/* 
        PURE RESOLUTION-INDEPENDENT 45° CRIMSON SLASH
        Uses CSS polygon clip-path with multi-stop wine/crimson gradient
        Exact angle and bounds matching reference:
        Top starts at ~81%, goes to 100%, right edge down to 24%,
        bottom band runs from 56% down to 24%.
      */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          clipPath: "polygon(56% 0%, 100% 0%, 100% 32%, 64% 100%, 25% 100%)",
          background: "linear-gradient(135deg, #A11A2C 0%, #8E1626 30%, #6E0F1C 65%, #4A0A14 100%)",
        }}
      />

      {/* Subtle diagonal sheen highlight */}
      <div
        className="pointer-events-none absolute inset-0 opacity-40 mix-blend-overlay"
        style={{
          clipPath: "polygon(56% 0%, 100% 0%, 100% 32%, 64% 100%, 25% 100%)",
          background:
            "linear-gradient(90deg, rgba(255,255,255,0.15) 0%, transparent 40%, rgba(0,0,0,0.4) 100%)",
        }}
      />

      {/* Subtle radial ambient atmosphere */}
      <div className="absolute inset-0 bg-radial-[circle_at_70%_40%] from-transparent via-transparent to-[#090D18]/60" />
    </div>
  );
}
