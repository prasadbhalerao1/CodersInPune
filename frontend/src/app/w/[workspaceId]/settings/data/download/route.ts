import { relayText, RelayApiError } from "@/lib/relay-api";

/** Download the workspace export (JSON) or the audit log (CSV) as the signed-in admin. */
export async function GET(
  request: Request,
  { params }: RouteContext<"/w/[workspaceId]/settings/data/download">,
) {
  const { workspaceId } = await params;
  const audit = new URL(request.url).searchParams.get("kind") === "audit";
  const path = `/workspaces/${encodeURIComponent(workspaceId)}/${audit ? "audit/export.csv" : "export"}`;
  try {
    const body = await relayText(path);
    const stamp = new Date().toISOString().slice(0, 10);
    return new Response(body, {
      headers: {
        "Content-Type": audit ? "text/csv; charset=utf-8" : "application/json; charset=utf-8",
        "Content-Disposition": `attachment; filename="relay-${audit ? "audit" : "workspace"}-${stamp}.${audit ? "csv" : "json"}"`,
        "Cache-Control": "no-store",
      },
    });
  } catch (error) {
    if (error instanceof RelayApiError)
      return new Response(error.message, { status: error.status });
    throw error;
  }
}
