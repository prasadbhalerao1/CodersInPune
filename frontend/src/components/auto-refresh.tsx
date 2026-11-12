"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

/** Re-render the page every few seconds while something runs in the background. */
export function AutoRefresh({ active, every = 2500 }: { active: boolean; every?: number }) {
  const router = useRouter();
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(() => router.refresh(), every);
    return () => clearInterval(timer);
  }, [active, every, router]);
  return null;
}
