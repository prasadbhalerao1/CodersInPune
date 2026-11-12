import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";

// Shown for anything the API reports as missing, including workspaces the person is not a
// member of: Relay never distinguishes "doesn't exist" from "not yours".
export default function NotFound() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center">
      <p className="font-medium">Not found</p>
      <p className="text-muted-foreground max-w-sm text-sm">
        It doesn&apos;t exist, or you don&apos;t have access to it.
      </p>
      <Link href="/workspaces" className={buttonVariants({ variant: "outline", size: "sm" })}>
        Your workspaces
      </Link>
    </div>
  );
}
