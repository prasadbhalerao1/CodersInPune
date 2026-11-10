import { api, RelayApiError } from "@/lib/relay-api";

/** Download the case's handover pack as Markdown, exactly as the signed-in user may see it. */
export async function GET(
  _request: Request,
  { params }: RouteContext<"/w/[workspaceId]/cases/[caseId]/export">,
) {
  const { workspaceId, caseId } = await params;
  try {
    const markdown = await api.caseExport(workspaceId, caseId);
    return new Response(markdown, {
      headers: {
        "Content-Type": "text/markdown; charset=utf-8",
        "Content-Disposition": `attachment; filename="handover-${caseId}.md"`,
        "Cache-Control": "no-store",
      },
    });
  } catch (error) {
    if (error instanceof RelayApiError) {
      return new Response(error.message, { status: error.status });
    }
    throw error;
  }
}
