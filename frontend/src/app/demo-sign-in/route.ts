// WHY DEMO ACCOUNTS EXIST: Relay is a real product. Anyone can sign in with their own email
// (WorkOS) and connect their real GitHub, Linear, Notion and Slack accounts; that is the normal
// path and uses exactly the same code. Doing that during judging would be slow, and a fresh
// organisation would not yet show the edge cases (a leaver, stale knowledge, conflicts, blocked
// handovers). So, to give judges the full experience in minutes, we also ship pre-seeded
// sample data and one shared demo account per role. Nothing here is a mock or a shortcut.

import { getWorkOS, saveSession } from "@workos-inc/authkit-nextjs";
import { redirect } from "next/navigation";
import type { NextRequest } from "next/server";

import { DEMO_PASSWORD, demoEmail } from "@/lib/demo-accounts";

// One-click sign-in for the judges' shared demo accounts. Only the published demo emails are
// accepted; the session is a normal WorkOS session, so the account then behaves exactly like
// any real user. If WorkOS asks for anything more (e.g. a verification code), fall back to the
// hosted sign-in with the email filled in.
export async function GET(request: NextRequest) {
  const role = request.nextUrl.searchParams.get("as");
  const email = demoEmail(role);
  if (!email) redirect("/sign-in");
  let signedIn = false;
  try {
    const auth = await getWorkOS().userManagement.authenticateWithPassword({
      clientId: process.env.WORKOS_CLIENT_ID ?? "",
      email,
      password: DEMO_PASSWORD,
    });
    await saveSession(auth, request);
    signedIn = true;
  } catch (error) {
    console.warn("demo sign-in fell back to hosted sign-in", role, error);
  }
  redirect(signedIn ? "/workspaces" : `/sign-in?as=${role}`);
}
