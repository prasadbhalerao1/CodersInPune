import type { ReactNode } from "react";
import { Suspense } from "react";

import { SidebarNav } from "@/components/sidebar-nav";
import { WorkspaceHeading } from "@/components/workspace-heading";
import { UserMenu } from "@/components/user-menu";

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-full">
      <aside
        aria-label="Primary"
        className="bg-muted/40 hidden w-60 shrink-0 flex-col border-r md:flex"
      >
        <div className="flex h-14 items-center border-b px-4">
          <Suspense fallback={<span className="text-sm font-semibold">Relay</span>}>
            <WorkspaceHeading />
          </Suspense>
        </div>
        <Suspense fallback={<div className="flex-1" />}>
          <SidebarNav />
        </Suspense>
        <div className="border-t p-4">
          <Suspense fallback={<span className="text-muted-foreground text-sm">…</span>}>
            <UserMenu />
          </Suspense>
        </div>
      </aside>
      <main className="flex min-w-0 flex-1 flex-col">{children}</main>
    </div>
  );
}
