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
  const name = user.firstName ? `${user.firstName} ${user.lastName ?? ""}`.trim() : user.email;
  const initials =
    (user.firstName?.[0] ?? user.email[0] ?? "?").toUpperCase() +
    (user.lastName?.[0] ?? "").toUpperCase();
  return (
    <div className="flex items-center gap-2.5 text-sm">
      <span
        aria-hidden
        className="bg-accent text-accent-foreground flex size-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold"
      >
        {initials}
      </span>
      <div className="flex min-w-0 flex-1 flex-col">
        <span className="truncate leading-tight font-medium" title={user.email}>
          {name}
        </span>
        <span className="text-muted-foreground flex gap-2 text-xs">
          <a href="/invitations" className="hover:text-foreground">
            Invitations
          </a>
          <span aria-hidden>·</span>
          <form action={signOutAction}>
            <button type="submit" className="hover:text-foreground">
              Sign out
            </button>
          </form>
        </span>
      </div>
    </div>
  );
}
