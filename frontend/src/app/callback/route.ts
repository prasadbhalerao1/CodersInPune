import { handleAuth } from "@workos-inc/authkit-nextjs";

// After sign-in, record the user's display name/email on their Relay memberships so
// teammates see who is assigned. Display-only; failures never block sign-in.
export const GET = handleAuth({
  returnPathname: "/workspaces",
  onSuccess: async ({ user, accessToken }) => {
    const base = process.env.RELAY_API_URL?.replace(/\/$/, "");
    if (!base) return;
    const display_name = [user.firstName, user.lastName].filter(Boolean).join(" ") || undefined;
    await fetch(`${base}/me/profile`, {
      method: "PUT",
      headers: { Authorization: `Bearer ${accessToken}`, "Content-Type": "application/json" },
      body: JSON.stringify({ display_name, email: user.email }),
    }).catch(() => undefined);
  },
});
