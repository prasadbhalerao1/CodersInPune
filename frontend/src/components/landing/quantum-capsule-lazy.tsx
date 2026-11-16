"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

import { QuantumCapsule } from "@/components/landing/quantum-capsule";

// three.js and the fluid simulation are the heaviest code on the landing page, so they load
// once the browser is idle and the page is already interactive. Until then the space stays
// empty and the 3D capsule fades in once: a different-looking stand-in that is swapped out
// would read as the page changing its mind. People who prefer reduced motion get the light
// CSS capsule, which never animates in.
const QuantumCapsule3D = dynamic(
  () => import("@/components/landing/quantum-capsule-3d").then((m) => m.QuantumCapsule3D),
  { ssr: false, loading: () => <Placeholder /> },
);

function Placeholder() {
  // Same box as the 3D canvas (aspect 820:620), so nothing shifts when it arrives.
  return <div aria-hidden className="mx-auto aspect-[820/620] w-full max-w-[820px]" />;
}

export function QuantumCapsuleLazy() {
  const [mode, setMode] = useState<"wait" | "3d" | "still">("wait");

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      const still = window.setTimeout(() => setMode("still"), 0);
      return () => window.clearTimeout(still);
    }
    const idle = window.requestIdleCallback ?? ((cb: () => void) => window.setTimeout(cb, 600));
    const cancel = window.cancelIdleCallback ?? window.clearTimeout;
    const handle = idle(() => setMode("3d"), { timeout: 1200 });
    return () => cancel(handle);
  }, []);

  if (mode === "still") return <QuantumCapsule />;
  if (mode === "wait") return <Placeholder />;
  return (
    <div className="animate-[capsule-in_700ms_cubic-bezier(0.2,0.8,0.2,1)_both]">
      <QuantumCapsule3D />
    </div>
  );
}
