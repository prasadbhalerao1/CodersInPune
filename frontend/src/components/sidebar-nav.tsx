"use client";

import {
  Activity,
  ArrowLeftRight,
  BookOpen,
  Bot,
  Boxes,
  Briefcase,
  ChartColumn,
  FileClock,
  FlaskConical,
  HelpCircle,
  Inbox,
  LayoutDashboard,
  ListChecks,
  Plug,
  Settings,
  ShieldAlert,
  Upload,
  Users,
  UsersRound,
  Workflow,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { useParams, usePathname } from "next/navigation";

import { useWorkspaceContext } from "@/components/workspace-context";
import type { WorkspaceRole } from "@/lib/types";
import { cn } from "@/lib/utils";

type Item = { label: string; path: string; icon: LucideIcon; roles?: readonly WorkspaceRole[] };

const ADMIN_ROLES: readonly WorkspaceRole[] = ["owner", "admin"];
// Mirrors `continuity.simulate` in relay/policy/permissions.py.
const SIMULATE_ROLES: readonly WorkspaceRole[] = [...ADMIN_ROLES, "continuity_manager"];

const GROUPS: readonly { label: string | null; items: readonly Item[] }[] = [
  {
    label: null,
    items: [
      { label: "Overview", path: "", icon: LayoutDashboard },
      { label: "My Work", path: "/my-work", icon: ListChecks },
      { label: "Inbox", path: "/inbox", icon: Inbox },
    ],
  },
  {
    label: "Continuity",
    items: [
      { label: "Cases", path: "/cases", icon: ArrowLeftRight },
      { label: "Responsibilities", path: "/responsibilities", icon: Briefcase },
      { label: "Risks", path: "/risks", icon: ShieldAlert },
      { label: "What-if simulator", path: "/simulator", icon: FlaskConical, roles: SIMULATE_ROLES },
    ],
  },
  {
    label: "Organisation",
    items: [
      { label: "People & Teams", path: "/people", icon: UsersRound },
      { label: "Knowledge", path: "/knowledge", icon: BookOpen },
      { label: "Assets", path: "/assets", icon: Boxes },
      {
        label: "Insights",
        path: "/insights",
        icon: ChartColumn,
        roles: [...ADMIN_ROLES, "auditor"],
      },
    ],
  },
  {
    label: "Workspace",
    items: [
      { label: "Members", path: "/members", icon: Users },
      { label: "Integrations", path: "/integrations", icon: Plug, roles: ADMIN_ROLES },
      { label: "Automations", path: "/automations", icon: Workflow, roles: ADMIN_ROLES },
      { label: "AI agents", path: "/agents", icon: Bot, roles: [...ADMIN_ROLES, "auditor"] },
      { label: "Import", path: "/import", icon: Upload, roles: ADMIN_ROLES },
      { label: "Audit log", path: "/audit", icon: FileClock, roles: [...ADMIN_ROLES, "auditor"] },
      { label: "Settings", path: "/settings", icon: Settings },
      { label: "Help", path: "/help", icon: HelpCircle },
    ],
  },
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
      <nav className="flex-1 p-3 text-sm">
        <NavLink href="/workspaces" icon={Activity} label="Workspaces" active />
      </nav>
    );
  }
  const base = `/w/${workspaceId}`;
  return (
    <nav aria-label="Workspace" className="flex flex-1 flex-col gap-5 overflow-y-auto p-3 text-sm">
      {GROUPS.map((group) => {
        const items = group.items.filter((item) => allowed(item.roles));
        if (items.length === 0) return null;
        return (
          <div key={group.label ?? "main"}>
            {group.label ? (
              <p className="text-muted-foreground/80 mb-1 px-2 text-[11px] font-medium tracking-wide uppercase">
                {group.label}
              </p>
            ) : null}
            <ul className="flex flex-col gap-px">
              {items.map(({ label, path, icon }) => {
                const href = base + path;
                const active = path ? pathname.startsWith(href) : pathname === base;
                return (
                  <li key={label}>
                    <NavLink href={href} icon={icon} label={label} active={active} />
                  </li>
                );
              })}
            </ul>
          </div>
        );
      })}
    </nav>
  );
}

function NavLink({
  href,
  icon: Icon,
  label,
  active,
}: {
  href: string;
  icon: LucideIcon;
  label: string;
  active: boolean;
}) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "relative flex items-center gap-2.5 rounded-md px-2 py-1.5 transition-colors",
        active
          ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium"
          : "text-sidebar-foreground/85 hover:bg-sidebar-accent/60 hover:text-sidebar-accent-foreground",
      )}
    >
      {active ? (
        <span aria-hidden className="bg-primary absolute inset-y-1.5 -left-3 w-0.5 rounded-r" />
      ) : null}
      <Icon
        aria-hidden
        className={cn("size-4 shrink-0", active ? "text-primary" : "text-muted-foreground")}
      />
      <span className="truncate">{label}</span>
    </Link>
  );
}
