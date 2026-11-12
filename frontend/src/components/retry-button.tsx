"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";

/** Re-render the current page: safe for reads, which is all an error notice can retry. */
export function RetryButton() {
  const router = useRouter();
  const [pending, start] = useTransition();
  return (
    <button
      type="button"
      onClick={() => start(() => router.refresh())}
      disabled={pending}
      className="underline disabled:opacity-60"
    >
      {pending ? "Retrying…" : "Try again"}
    </button>
  );
}
