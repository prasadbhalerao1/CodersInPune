"use client";

import Link from "next/link";
import { useParams } from "next/navigation";

import { useWorkspaceContext } from "@/components/workspace-context";

/** Which workspace you're acting in, with a way back to the switcher. */
export function WorkspaceHeading() {
  const { workspaceId } = useParams<{ workspaceId?: string }>();
  const context = useWorkspaceContext();
  const name = workspaceId && context?.workspaceId === workspaceId ? context.name : null;
  return (
    <Link href="/workspaces" className="min-w-0 truncate" title="Switch workspace">
      <span className="text-muted-foreground block text-[11px] leading-none">Relay</span>
      <span className="block truncate text-sm font-semibold">{name ?? "Workspaces"}</span>
    </Link>
  );
}
