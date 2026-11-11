import type { ReactNode } from "react";
import { Suspense } from "react";

import { CommandMenu, CommandTrigger } from "@/components/command-menu";
import { SidebarNav } from "@/components/sidebar-nav";
import { WorkspaceHeading } from "@/components/workspace-heading";
import { UserMenu } from "@/components/user-menu";

export function AppShell({ children }: { children: ReactNode }) {
  const sidebar = (
    <aside
      aria-label="Primary"
      className="bg-sidebar text-sidebar-foreground border-sidebar-border sticky top-0 hidden h-dvh w-64 shrink-0 flex-col border-r md:flex"
    >
      <div className="flex h-14 items-center px-4">
        <Suspense fallback={<span className="text-sm font-semibold">Relay</span>}>
          <WorkspaceHeading />
        </Suspense>
      </div>
      <Suspense fallback={null}>
        <CommandTrigger />
      </Suspense>
      <Suspense fallback={<div className="flex-1" />}>
        <SidebarNav />
      </Suspense>
      <div className="border-sidebar-border border-t p-3">
        <Suspense fallback={<span className="text-muted-foreground text-sm">…</span>}>
          <UserMenu />
        </Suspense>
      </div>
    </aside>
  );
  return (
    <>
      <div className="flex min-h-full">
        {sidebar}
        <main className="flex min-h-dvh min-w-0 flex-1 flex-col">{children}</main>
      </div>
      <Suspense fallback={null}>
        <CommandMenu />
      </Suspense>
    </>
  );
}
