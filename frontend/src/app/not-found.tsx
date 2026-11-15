import type { Metadata } from "next";

import { ErrorScreen } from "@/components/error-screen";

export const metadata: Metadata = { title: "Page not found" };

export default function NotFound() {
  return (
    <ErrorScreen code="404" title="This page has moved on" full>
      The address may be mistyped, or the page was handed over to somewhere else. Nothing you own
      has changed.
    </ErrorScreen>
  );
}
