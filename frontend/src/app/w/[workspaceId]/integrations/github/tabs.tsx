import Link from "next/link";

import { cn } from "@/lib/utils";

const TABS = [
  { key: "overview", label: "Connection", path: "" },
  { key: "suggestions", label: "Suggestions", path: "/github/suggestions" },
  { key: "identities", label: "People", path: "/github/identities" },
  { key: "teams", label: "Teams", path: "/github/teams" },
  { key: "signals", label: "Signals", path: "/github/signals" },
] as const;

export type GitHubTab = (typeof TABS)[number]["key"];

export function GitHubTabs({
  workspaceId,
  current,
  counts = {},
}: {
  workspaceId: string;
  current: GitHubTab;
  counts?: Partial<Record<GitHubTab, number>>;
}) {
  const base = `/w/${workspaceId}/integrations`;
  return (
    <nav aria-label="GitHub" className="flex gap-1 border-b px-6 text-sm">
      {TABS.map((t) => (
        <Link
          key={t.key}
          href={base + t.path}
          aria-current={current === t.key ? "page" : undefined}
          className={cn(
            "-mb-px flex items-center gap-1.5 border-b-2 px-2.5 py-2.5",
            current === t.key
              ? "border-foreground font-medium"
              : "text-muted-foreground hover:text-foreground border-transparent",
          )}
        >
          {t.label}
          {counts[t.key] ? (
            <span className="bg-foreground/[0.07] rounded px-1.5 text-xs tabular-nums">
              {counts[t.key]}
            </span>
          ) : null}
        </Link>
      ))}
    </nav>
  );
}
