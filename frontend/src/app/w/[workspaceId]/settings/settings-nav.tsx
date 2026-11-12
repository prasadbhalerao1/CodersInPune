import Link from "next/link";

import { cn } from "@/lib/utils";

const TABS = [
  { key: "general", label: "Policies", path: "", admin: true },
  { key: "governance", label: "Types & tiers", path: "/governance", admin: false },
  { key: "roles", label: "Roles & access", path: "/roles", admin: false },
  { key: "data", label: "Data & privacy", path: "/data", admin: false },
  { key: "members", label: "Members", path: "/members", admin: false, absolute: true },
  { key: "notifications", label: "Notifications", path: "/notifications", admin: false },
  {
    key: "integrations",
    label: "Integrations",
    path: "/integrations",
    admin: true,
    absolute: true,
  },
  { key: "automations", label: "Automations", path: "/automations", admin: true, absolute: true },
  { key: "audit", label: "Audit log", path: "/audit", admin: true, absolute: true },
] as const;

export type SettingsTab = (typeof TABS)[number]["key"];

/** One settings experience: tabs link to the existing admin areas. */
export function SettingsNav({
  workspaceId,
  current,
  admin,
}: {
  workspaceId: string;
  current: SettingsTab;
  admin: boolean;
}) {
  const ws = `/w/${workspaceId}`;
  return (
    <nav aria-label="Settings" className="flex gap-1 overflow-x-auto border-b px-6 text-sm">
      {TABS.filter((t) => admin || !t.admin).map((t) => (
        <Link
          key={t.key}
          href={"absolute" in t && t.absolute ? ws + t.path : `${ws}/settings${t.path}`}
          aria-current={current === t.key ? "page" : undefined}
          className={cn(
            "-mb-px border-b-2 px-2.5 py-2.5 whitespace-nowrap",
            current === t.key
              ? "border-foreground font-medium"
              : "text-muted-foreground hover:text-foreground border-transparent",
          )}
        >
          {t.label}
        </Link>
      ))}
    </nav>
  );
}
