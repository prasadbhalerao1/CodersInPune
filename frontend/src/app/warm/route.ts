import { after } from "next/server";

/**
 * Wakes the API while a visitor is still reading the landing page, so the first click into
 * the app doesn't wait for a cold start. Answers at once; the ping runs after the response.
 * Public and side-effect free: it only touches the API's liveness probe.
 */
export function POST() {
  const api = process.env.RELAY_API_URL?.replace(/\/$/, "");
  if (api) {
    after(async () => {
      await fetch(`${api}/health/live`, {
        cache: "no-store",
        signal: AbortSignal.timeout(60_000),
      }).catch(() => undefined);
    });
  }
  return new Response(null, { status: 204 });
}
