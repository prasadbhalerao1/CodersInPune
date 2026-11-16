"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

import { QuantumCapsule } from "@/components/landing/quantum-capsule";

// three.js and the fluid simulation are the heaviest code on the landing page. Show the
// light CSS capsule first and swap in the 3D one once the browser is idle, so the page is
// interactive at once; people who prefer reduced motion keep the CSS capsule.
const QuantumCapsule3D = dynamic(
  () => import("@/components/landing/quantum-capsule-3d").then((m) => m.QuantumCapsule3D),
  { ssr: false, loading: () => <QuantumCapsule /> },
);

export function QuantumCapsuleLazy() {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const idle = window.requestIdleCallback ?? ((cb: () => void) => window.setTimeout(cb, 1200));
    const cancel = window.cancelIdleCallback ?? window.clearTimeout;
    const handle = idle(() => setReady(true), { timeout: 2500 });
    return () => cancel(handle);
  }, []);

  return ready ? <QuantumCapsule3D /> : <QuantumCapsule />;
}
