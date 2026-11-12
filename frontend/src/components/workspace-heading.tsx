"use client";

import { ChevronsUpDown } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { useWorkspaceContext } from "@/components/workspace-context";

/** The Relay mark: two offset strokes, one handing over to the other. */
export function RelayMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden className={className}>
      <rect width="24" height="24" rx="6" className="fill-primary" />
      <path
        d="M7 15.5h6.5a3 3 0 0 0 0-6H9.5"
        className="stroke-primary-foreground"
        strokeWidth="2"
        strokeLinecap="round"
        fill="none"
      />
      <path
        d="M11.5 15.5 17 15.5"
        className="stroke-primary-foreground/60"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}

/** Which workspace you're acting in, with a way back to the switcher. */
export function WorkspaceHeading() {
  const { workspaceId } = useParams<{ workspaceId?: string }>();
  const context = useWorkspaceContext();
  const name = workspaceId && context?.workspaceId === workspaceId ? context.name : null;
  return (
    <Link
      href="/workspaces"
      title="Switch workspace"
      className="hover:bg-sidebar-accent/70 -mx-1.5 flex min-w-0 flex-1 items-center gap-2.5 rounded-md px-1.5 py-1"
    >
      <RelayMark className="size-7 shrink-0" />
      <span className="min-w-0 flex-1">
        <span className="text-muted-foreground block text-[11px] leading-tight">Relay</span>
        <span className="block truncate text-sm leading-tight font-semibold">
          {name ?? "Workspaces"}
        </span>
      </span>
      <ChevronsUpDown aria-hidden className="text-muted-foreground size-3.5 shrink-0" />
    </Link>
  );
}
