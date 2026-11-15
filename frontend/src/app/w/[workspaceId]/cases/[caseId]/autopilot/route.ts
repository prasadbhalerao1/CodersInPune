import { proxyStream } from "@/lib/stream-proxy";

/** Handover Autopilot's steps, streamed from the API as they happen. */
export async function POST(
  request: Request,
  { params }: RouteContext<"/w/[workspaceId]/cases/[caseId]/autopilot">,
) {
  const { workspaceId, caseId } = await params;
  return proxyStream(
    request,
    `/workspaces/${workspaceId}/cases/${caseId}/autopilot`,
    [workspaceId, caseId],
    "Autopilot could not start.",
  );
}
