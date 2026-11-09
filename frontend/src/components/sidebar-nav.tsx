"use client";

import Link from "next/link";
import { useParams, usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const LIVE = [
  { label: "Overview", path: "" },
  { label: "My Work", path: "/my-work" },
  { label: "Inbox", path: "/inbox" },
  { label: "Cases", path: "/cases" },
  { label: "Responsibilities", path: "/responsibilities" },
  { label: "Assets", path: "/assets" },
  { label: "Knowledge", path: "/knowledge" },
  { label: "Risks", path: "/risks" },
  { label: "Insights", path: "/insights" },
  { label: "People & Teams", path: "/people" },
] as const;
const SETTINGS = [
  { label: "Members", path: "/members" },
  { label: "Integrations", path: "/integrations" },
  { label: "Import", path: "/import" },
  { label: "Audit log", path: "/audit" },
] as const;

export function SidebarNav() {
  const { workspaceId } = useParams<{ workspaceId?: string }>();
  const pathname = usePathname();
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
        {LIVE.map(({ label, path }) => {
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
          {SETTINGS.map(({ label, path }) => {
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
