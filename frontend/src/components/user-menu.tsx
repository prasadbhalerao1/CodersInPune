import { withAuth } from "@workos-inc/authkit-nextjs";

import { signOutAction } from "@/app/actions";

export async function UserMenu() {
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
      <form action={signOutAction}>
        <button type="submit" className="text-muted-foreground hover:underline">
          Sign out
        </button>
      </form>
    </div>
  );
}
