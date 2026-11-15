import { relayStream } from "@/lib/relay-api";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * Passes an API's server-sent events straight through (returned at once, never buffered),
 * and stops the upstream work when the reader goes away. `ids` are checked as UUIDs first.
 */
export async function proxyStream(
  request: Request,
  path: string,
  ids: string[],
  fallback = "The request could not be sent.",
) {
  if (!ids.every((id) => UUID.test(id))) {
    return Response.json({ detail: "Not found" }, { status: 404 });
  }
  const upstream = await relayStream(path, await request.text(), request.signal);
  if (!upstream.ok || !upstream.body) {
    const problem = (await upstream.json().catch(() => ({}))) as { detail?: unknown };
    const detail = typeof problem.detail === "string" ? problem.detail : fallback;
    return Response.json({ detail }, { status: upstream.status || 502 });
  }
  return new Response(upstream.body, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      "X-Accel-Buffering": "no",
    },
  });
}
