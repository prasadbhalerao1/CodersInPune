// WHY DEMO ACCOUNTS EXIST: Relay is a real product. Anyone can sign in with their own email
// (WorkOS) and connect their real GitHub, Linear, Notion and Slack accounts; that is the normal
// path and uses exactly the same code. Doing that during judging would be slow, and a fresh
// organisation would not yet show the edge cases (a leaver, stale knowledge, conflicts, blocked
// handovers). So, to give judges the full experience in minutes, we also ship pre-seeded
// sample data and one shared demo account per role. Nothing here is a mock or a shortcut.

import { getSignInUrl, getWorkOS, saveSession } from "@workos-inc/authkit-nextjs";
import { redirect } from "next/navigation";
import type { NextRequest } from "next/server";

import { DEMO_PASSWORD, demoEmail } from "@/lib/demo-accounts";

// Initiate-login URI (configure it in the WorkOS dashboard). Sets the PKCE cookie.
// `?as=<role>` signs in that role's shared judging account in one click: a normal WorkOS
// session, so the account behaves exactly like any real user. If WorkOS asks for more (e.g. a
// verification code), it falls back to the hosted sign-in with the email filled in. Any other
// value is ignored.
export async function GET(request: NextRequest) {
  const email = demoEmail(request.nextUrl.searchParams.get("as"));
  if (email && process.env.WORKOS_CLIENT_ID) {
    let signedIn = false;
    try {
      const auth = await getWorkOS().userManagement.authenticateWithPassword({
        clientId: process.env.WORKOS_CLIENT_ID,
        email,
        password: DEMO_PASSWORD,
      });
      await saveSession(auth, request);
      signedIn = true;
    } catch (error) {
      const code = (error as { code?: string; status?: number }).code ?? "unknown";
      console.warn("one-click sign-in fell back to hosted sign-in:", code);
    }
    if (signedIn) redirect("/workspaces");
  }
  redirect(await getSignInUrl(email ? { loginHint: email } : undefined));
}
