import Link from "next/link";
import { Suspense } from "react";

import { MobileSearchButton } from "@/components/command-menu";
import { formatDateTime } from "@/components/page";
import { SampleBanner } from "@/components/sample-banner";
import { SidebarNav } from "@/components/sidebar-nav";
import { TourRunner } from "@/components/tour";
import { WorkspaceContextBridge } from "@/components/workspace-context";
import { api, RelayApiError } from "@/lib/relay-api";
import type { WorkspaceRole } from "@/lib/types";

/**
 * API errors leave the chrome out (the page below shows them, with a retry). Server errors are
 * logged so they are not silent; anything that isn't an API error is a bug and reaches error.tsx.
 */
async function optional<T>(request: Promise<T>): Promise<T | null> {
  try {
    return await request;
  } catch (error) {
    if (!(error instanceof RelayApiError)) throw error;
    if (error.status >= 500)
      console.error("workspace chrome unavailable:", error.status, error.code);
    return null;
  }
}

async function WorkspaceChrome({ params }: { params: Promise<{ workspaceId: string }> }) {
  const { workspaceId } = await params;
  // Not attempt(): its notFound() would escape this segment's not-found page from a
  // layout. Chrome is optional; the page itself explains a missing or forbidden workspace.
  const [workspace, sample] = await Promise.all([
    optional(api.getWorkspace(workspaceId)),
    optional(api.demoRole(workspaceId)),
  ]);
  if (!workspace) return null;
  const { name, role, deletion_scheduled_for: deletionAt } = workspace;
  return (
    <>
      <WorkspaceContextBridge workspaceId={workspaceId} name={name} role={role as WorkspaceRole} />
      {/* Phones and small tablets: the sidebar is hidden, so navigation lives here. */}
      <div className="flex items-start border-b md:hidden">
        <details className="group min-w-0 flex-1">
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
        <MobileSearchButton />
      </div>
      {sample?.sample ? <SampleBanner workspaceId={workspaceId} view={sample} /> : null}
      {deletionAt ? (
        <p
          role="status"
          className="border-b border-amber-600/20 bg-amber-50 px-4 py-2 text-sm text-amber-950 dark:bg-amber-950/30 dark:text-amber-100"
        >
          This workspace will be permanently deleted on {formatDateTime(deletionAt)}.{" "}
          <Link href={`/w/${workspaceId}/settings/data#delete`} className="font-medium underline">
            {role === "owner" ? "Cancel deletion or export data" : "Export what you need"}
          </Link>
        </p>
      ) : null}
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
      <Suspense fallback={null}>
        <TourRunner />
      </Suspense>
    </>
  );
}
