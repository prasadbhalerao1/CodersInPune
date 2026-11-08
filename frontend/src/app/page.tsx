import { withAuth } from "@workos-inc/authkit-nextjs";
import Link from "next/link";
import { Suspense } from "react";

export default function HomePage() {
  return (
    <section className="flex flex-1 items-center justify-center p-6">
      <div className="max-w-md text-center">
        <h1 className="text-lg font-semibold">Relay</h1>
        <p className="text-muted-foreground mt-2 text-sm">
          Keep work moving when people, projects and responsibilities change.
        </p>
        <div className="mt-6">
          <Suspense fallback={null}>
            <PrimaryAction />
          </Suspense>
        </div>
      </div>
    </section>
  );
}

async function PrimaryAction() {
  const { user } = await withAuth();
  const className =
    "bg-primary text-primary-foreground inline-flex h-9 items-center rounded-lg px-4 text-sm font-medium";
  if (user) {
    return (
      <Link href="/workspaces" className={className}>
        Go to your workspaces
      </Link>
    );
  }
  // A plain link (not prefetched) so navigation, not prefetching, starts sign-in.
  return (
    <a href="/sign-in" className={className}>
      Sign in
    </a>
  );
}
