import { relayStream } from "@/lib/relay-api";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * Copilot answers as they are written: passes the API's server-sent events straight through
 * (returned at once, never buffered), and stops the model when the reader goes away.
 */
export async function POST(
  request: Request,
  { params }: RouteContext<"/w/[workspaceId]/cases/[caseId]/capsules/[capsuleId]/ask">,
) {
  const { workspaceId, capsuleId } = await params;
  if (!UUID.test(workspaceId) || !UUID.test(capsuleId)) {
    return Response.json({ detail: "Not found" }, { status: 404 });
  }
  const upstream = await relayStream(
    `/workspaces/${workspaceId}/ai/capsules/${capsuleId}/questions/stream`,
    await request.text(),
    request.signal,
  );
  if (!upstream.ok || !upstream.body) {
    const problem = (await upstream.json().catch(() => ({}))) as { detail?: unknown };
    const detail =
      typeof problem.detail === "string" ? problem.detail : "The question could not be sent.";
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
