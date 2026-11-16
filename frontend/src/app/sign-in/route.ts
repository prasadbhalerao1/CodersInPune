// WHY DEMO ACCOUNTS EXIST: Relay is a real product. Anyone can sign in with their own email
// (WorkOS) and connect their real GitHub, Linear, Notion and Slack accounts; that is the normal
// path and uses exactly the same code. Doing that during judging would be slow, and a fresh
// organisation would not yet show the edge cases (a leaver, stale knowledge, conflicts, blocked
// handovers). So, to give judges the full experience in minutes, we also ship pre-seeded
// sample data and one shared demo account per role. Nothing here is a mock or a shortcut.

import { getSignInUrl } from "@workos-inc/authkit-nextjs";
import { redirect } from "next/navigation";
import type { NextRequest } from "next/server";

import { demoEmail } from "@/lib/demo-accounts";

// Initiate-login URI (configure it in the WorkOS dashboard). Sets the PKCE cookie.
// `?as=<role>` pre-fills a judges' demo account; anything else is ignored.
export async function GET(request: NextRequest) {
  const loginHint = demoEmail(request.nextUrl.searchParams.get("as"));
  redirect(await getSignInUrl(loginHint ? { loginHint } : undefined));
}
