import type { ReactNode } from "react";
import { Suspense } from "react";

import { CommandMenu, CommandTrigger } from "@/components/command-menu";
import { NavProgress } from "@/components/nav-progress";
import { SidebarFrame } from "@/components/sidebar-frame";
import { SidebarNav } from "@/components/sidebar-nav";
import { WorkspaceHeading } from "@/components/workspace-heading";
import { UserMenu } from "@/components/user-menu";

export function AppShell({ children }: { children: ReactNode }) {
  const sidebar = (
    <SidebarFrame>
      <div className="flex h-14 items-center overflow-hidden px-4">
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
      <div className="border-sidebar-border overflow-hidden border-t p-3">
        <Suspense fallback={<span className="text-muted-foreground text-sm">…</span>}>
          <UserMenu />
        </Suspense>
      </div>
    </SidebarFrame>
  );
  return (
    <>
      <div className="flex min-h-full">
        {sidebar}
        <main className="flex min-h-dvh min-w-0 flex-1 flex-col">
          {/* Very wide screens: the page stays one comfortable, centred column. */}
          <div className="mx-auto flex w-full max-w-[105rem] flex-1 flex-col">{children}</div>
        </main>
      </div>
      <Suspense fallback={null}>
        <CommandMenu />
      </Suspense>
      <Suspense fallback={null}>
        <NavProgress />
      </Suspense>
    </>
  );
}
