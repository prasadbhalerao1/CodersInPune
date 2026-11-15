import { proxyStream } from "@/lib/stream-proxy";

/** Ask Relay's answer, streamed from the API as it is written. */
export async function POST(request: Request, { params }: RouteContext<"/w/[workspaceId]/ask/stream">) {
  const { workspaceId } = await params;
  return proxyStream(
    request,
    `/workspaces/${workspaceId}/ask`,
    [workspaceId],
    "The question could not be sent.",
  );
}
