"use client";

import { useLinkStatus } from "next/link";

/**
 * Place inside a `<Link>`: a shimmer over the link while its navigation is pending, so a tab or
 * filter answers the click at once even when the server takes a moment.
 */
export function LinkPending() {
  const { pending } = useLinkStatus();
  return <span aria-hidden className="link-pending" data-pending={pending} />;
}
