import { withAuth } from "@workos-inc/authkit-nextjs";
import { type NextRequest, NextResponse } from "next/server";

// GitHub redirects here after installation (configure as the App's Callback URL, with
// "Request user authorization (OAuth) during installation" enabled). The API verifies the
// state and that the installation belongs to the GitHub user; nothing is trusted here.
export async function GET(request: NextRequest) {
  const params = request.nextUrl.searchParams;
  const state = params.get("state") ?? "";
  const code = params.get("code") ?? "";
  const installationId = Number(params.get("installation_id"));
  const workspaceId = state.split(".")[0] ?? "";
  const back = (query: string) =>
    NextResponse.redirect(new URL(`/w/${workspaceId}/integrations?${query}`, request.url));

  if (
    !state ||
    !code ||
    !Number.isSafeInteger(installationId) ||
    !/^[0-9a-f-]{36}$/.test(workspaceId)
  ) {
    return NextResponse.redirect(new URL("/workspaces", request.url));
  }
  const { accessToken } = await withAuth({ ensureSignedIn: true });
  const base = process.env.RELAY_API_URL?.replace(/\/$/, "");
  const response = await fetch(`${base}/integrations/github/complete`, {
    method: "POST",
    headers: { Authorization: `Bearer ${accessToken}`, "Content-Type": "application/json" },
    body: JSON.stringify({ state, code, installation_id: installationId }),
    cache: "no-store",
  }).catch(() => null);
  if (!response?.ok) {
    const problem = (await response?.json().catch(() => null)) as { detail?: string } | null;
    return back(`error=${encodeURIComponent(problem?.detail ?? "GitHub could not be connected.")}`);
  }
  return back("connected=1");
}
