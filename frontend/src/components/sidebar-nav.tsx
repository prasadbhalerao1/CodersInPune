"use client";

import Link from "next/link";
import { useParams, usePathname } from "next/navigation";

import { useWorkspaceContext } from "@/components/workspace-context";
import type { WorkspaceRole } from "@/lib/types";
import { cn } from "@/lib/utils";

const ADMIN_ROLES: readonly WorkspaceRole[] = ["owner", "admin"];
const LIVE: readonly { label: string; path: string; roles?: readonly WorkspaceRole[] }[] = [
  { label: "Overview", path: "" },
  { label: "My Work", path: "/my-work" },
  { label: "Inbox", path: "/inbox" },
  { label: "Cases", path: "/cases" },
  { label: "Responsibilities", path: "/responsibilities" },
  { label: "Assets", path: "/assets" },
  { label: "Knowledge", path: "/knowledge" },
  { label: "Risks", path: "/risks" },
  { label: "Insights", path: "/insights", roles: [...ADMIN_ROLES, "auditor"] },
  { label: "People & Teams", path: "/people" },
];
const SETTINGS: readonly { label: string; path: string; roles?: readonly WorkspaceRole[] }[] = [
  { label: "Members", path: "/members" },
  { label: "Integrations", path: "/integrations", roles: ADMIN_ROLES },
  { label: "Automations", path: "/automations", roles: ADMIN_ROLES },
  { label: "Agents", path: "/agents", roles: [...ADMIN_ROLES, "auditor"] },
  { label: "Import", path: "/import", roles: ADMIN_ROLES },
  { label: "Settings", path: "/settings" },
  { label: "Audit log", path: "/audit", roles: [...ADMIN_ROLES, "auditor"] },
  { label: "Help", path: "/help" },
];

export function SidebarNav() {
  const { workspaceId } = useParams<{ workspaceId?: string }>();
  const pathname = usePathname();
  const context = useWorkspaceContext();
  // Until the role is known, hide role-restricted links rather than flash them.
  const allowed = (roles?: readonly WorkspaceRole[]) =>
    !roles ||
    (context !== null && context.workspaceId === workspaceId && roles.includes(context.role));
  if (!workspaceId) {
    return (
      <nav className="p-3 text-sm">
        <Link href="/workspaces" className="hover:bg-muted block rounded-md px-2 py-1.5">
          Workspaces
        </Link>
      </nav>
    );
  }
  const base = `/w/${workspaceId}`;
  return (
    <nav aria-label="Workspace" className="flex flex-1 flex-col gap-6 p-3 text-sm">
      <ul className="flex flex-col gap-0.5">
        {LIVE.filter((item) => allowed(item.roles)).map(({ label, path }) => {
          const href = base + path;
          const active = path ? pathname.startsWith(href) : pathname === base;
          return (
            <li key={label}>
              <Link
                href={href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "block rounded-md px-2 py-1.5 transition-colors",
                  active ? "bg-foreground/[0.06] font-medium" : "hover:bg-muted text-foreground/80",
                )}
              >
                {label}
              </Link>
            </li>
          );
        })}
      </ul>
      <div>
        <p className="text-muted-foreground mb-1 px-2 text-xs font-medium">Workspace</p>
        <ul className="flex flex-col gap-0.5">
          {SETTINGS.filter((item) => allowed(item.roles)).map(({ label, path }) => {
            const href = base + path;
            const active = pathname.startsWith(href);
            return (
              <li key={label}>
                <Link
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "block rounded-md px-2 py-1.5 transition-colors",
                    active
                      ? "bg-foreground/[0.06] font-medium"
                      : "hover:bg-muted text-foreground/80",
                  )}
                >
                  {label}
                </Link>
              </li>
            );
          })}
        </ul>
      </div>
      <Link
        href="/workspaces"
        className="text-muted-foreground mt-auto px-2 text-xs hover:underline"
      >
        Switch workspace
      </Link>
    </nav>
  );
}
