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
