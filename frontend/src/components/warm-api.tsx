"use client";

import { useEffect } from "react";

/** Once per page load: ask the server to wake the API (see `app/warm/route.ts`). */
export function WarmApi() {
  useEffect(() => {
    try {
      navigator.sendBeacon("/warm");
    } catch {
      // Best effort only.
    }
  }, []);
  return null;
}
