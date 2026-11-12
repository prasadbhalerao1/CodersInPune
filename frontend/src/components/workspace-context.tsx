"use client";

import { useEffect, useSyncExternalStore } from "react";

import type { WorkspaceRole } from "@/lib/types";

/**
 * The sidebar lives in the root layout and can't receive workspace data as props. The
 * workspace layout (server) publishes the current workspace's name and the viewer's role
 * here; the sidebar reads it to show only what the role can use. Display only: the API
 * enforces every permission.
 */
type Context = { workspaceId: string; name: string; role: WorkspaceRole } | null;

let current: Context = null;
const listeners = new Set<() => void>();

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useWorkspaceContext(): Context {
  return useSyncExternalStore(
    subscribe,
    () => current,
    () => null,
  );
}

export function WorkspaceContextBridge({
  workspaceId,
  name,
  role,
}: {
  workspaceId: string;
  name: string;
  role: WorkspaceRole;
}) {
  useEffect(() => {
    current = { workspaceId, name, role };
    listeners.forEach((l) => l());
  }, [workspaceId, name, role]);
  return null;
}
