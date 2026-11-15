"use client";

import { useEffect, useState } from "react";

/**
 * Silent for a normal load; after a few seconds explains the wait, and much later offers a
 * reload, so a slow response never looks like a frozen page.
 */
export function SlowHint() {
  const [stage, setStage] = useState(0);
  useEffect(() => {
    const timers = [setTimeout(() => setStage(1), 3500), setTimeout(() => setStage(2), 20000)];
    return () => timers.forEach(clearTimeout);
  }, []);
  if (stage === 0) return null;
  return (
    <p
      role="status"
      className="slow-hint text-muted-foreground flex items-center gap-2 px-6 pt-4 text-sm"
    >
      <span aria-hidden className="copilot-pulse" />
      {stage === 1 ? (
        "Still loading. The first request after a quiet spell can take a few seconds."
      ) : (
        <>
          This is taking longer than usual.
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="text-foreground underline underline-offset-2"
          >
            Reload
          </button>
        </>
      )}
    </p>
  );
}
