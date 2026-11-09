import { Suspense } from "react";

import { SidebarNav } from "@/components/sidebar-nav";
import { WorkspaceContextBridge } from "@/components/workspace-context";
import { api } from "@/lib/relay-api";
import type { WorkspaceRole } from "@/lib/types";

async function WorkspaceChrome({ params }: { params: Promise<{ workspaceId: string }> }) {
  const { workspaceId } = await params;
  // Not attempt(): its notFound() would escape this segment's not-found page from a
  // layout. Chrome is optional; the page itself explains a missing or forbidden workspace.
  const workspace = await api.getWorkspace(workspaceId).catch(() => null);
  if (!workspace) return null;
  const { name, role } = workspace;
  return (
    <>
      <WorkspaceContextBridge workspaceId={workspaceId} name={name} role={role as WorkspaceRole} />
      {/* Phones and small tablets: the sidebar is hidden, so navigation lives here. */}
      <details className="group border-b md:hidden">
        <summary className="flex h-12 cursor-pointer list-none items-center gap-3 px-4 text-sm select-none">
          <span aria-hidden className="text-lg leading-none">
            ☰
          </span>
          <span className="min-w-0 flex-1 truncate font-semibold">{name}</span>
          <span className="text-muted-foreground text-xs capitalize">{role}</span>
        </summary>
        <div className="bg-muted/40 border-t">
          <SidebarNav />
        </div>
      </details>
    </>
  );
}

export default function WorkspaceLayout({ children, params }: LayoutProps<"/w/[workspaceId]">) {
  return (
    <>
      <Suspense fallback={<div className="h-12 border-b md:hidden" />}>
        <WorkspaceChrome params={params} />
      </Suspense>
      {children}
    </>
  );
}
