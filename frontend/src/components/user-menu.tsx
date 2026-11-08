import { withAuth } from "@workos-inc/authkit-nextjs";
import { connection } from "next/server";

import { signOutAction } from "@/app/actions";

export async function UserMenu() {
  // withAuth reads the clock for token expiry; mark the render as request-time first.
  await connection();
  const { user } = await withAuth();
  if (!user) {
    return (
      <a href="/sign-in" className="text-sm font-medium hover:underline">
        Sign in
      </a>
    );
  }
  return (
    <div className="flex flex-col gap-1 text-sm">
      <span className="truncate font-medium" title={user.email}>
        {user.firstName ? `${user.firstName} ${user.lastName ?? ""}`.trim() : user.email}
      </span>
      <a href="/invitations" className="text-muted-foreground hover:underline">
        Invitations
      </a>
      <form action={signOutAction}>
        <button type="submit" className="text-muted-foreground hover:underline">
          Sign out
        </button>
      </form>
    </div>
  );
}
