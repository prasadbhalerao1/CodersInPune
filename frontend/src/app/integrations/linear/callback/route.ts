import { withAuth } from "@workos-inc/authkit-nextjs";
import { type NextRequest, NextResponse } from "next/server";

// Linear redirects here after OAuth consent (register this as the OAuth app's callback
// URL). The API verifies the state (workspace, user, single use) and exchanges the code;
// nothing is trusted here.
export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams;
  const state = params.get("state") ?? "";
  const code = params.get("code") ?? "";
  const workspaceId = state.split(".")[0] ?? "";
  const back = (query: string) =>
    NextResponse.redirect(new URL(`/w/${workspaceId}/integrations/linear?${query}`, request.url));

  if (!state || !/^[0-9a-f-]{36}$/.test(workspaceId)) {
    return NextResponse.redirect(new URL("/workspaces", request.url));
  }
  if (!code) return back(`error=${encodeURIComponent("Linear access was not granted.")}`);
  const { accessToken } = await withAuth({ ensureSignedIn: true });
  const base = process.env.RELAY_API_URL?.replace(/\/$/, "");
  const response = await fetch(`${base}/integrations/linear/complete`, {
    method: "POST",
    headers: { Authorization: `Bearer ${accessToken}`, "Content-Type": "application/json" },
    body: JSON.stringify({ state, code }),
    cache: "no-store",
  }).catch(() => null);
  if (!response?.ok) {
    const problem = (await response?.json().catch(() => null)) as { detail?: string } | null;
    return back(`error=${encodeURIComponent(problem?.detail ?? "Linear could not be connected.")}`);
  }
  return back("connected=1");
}
