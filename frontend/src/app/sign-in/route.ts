import { getSignInUrl } from "@workos-inc/authkit-nextjs";
import { redirect } from "next/navigation";

// Initiate-login URI (configure it in the WorkOS dashboard). Sets the PKCE cookie.
export async function GET() {
  redirect(await getSignInUrl());
}
