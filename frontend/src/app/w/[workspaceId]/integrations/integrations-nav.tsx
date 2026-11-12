import Link from "next/link";

import { cn } from "@/lib/utils";

const PROVIDERS = [
  { key: "github", label: "GitHub", path: "" },
  { key: "linear", label: "Linear", path: "/linear" },
  { key: "notion", label: "Notion", path: "/notion" },
  { key: "health", label: "Health", path: "/health" },
] as const;

/** Consistent switcher across the integration providers. */
export function IntegrationsNav({
  workspaceId,
  current,
}: {
  workspaceId: string;
  current: (typeof PROVIDERS)[number]["key"];
}) {
  return (
    <nav aria-label="Integrations" className="flex gap-1 border-b px-6 pt-2 text-sm">
      {PROVIDERS.map((p) => (
        <Link
          key={p.key}
          href={`/w/${workspaceId}/integrations${p.path}`}
          aria-current={current === p.key ? "page" : undefined}
          className={cn(
            "rounded-t-md px-3 py-2",
            current === p.key
              ? "bg-foreground/[0.06] font-medium"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          {p.label}
        </Link>
      ))}
    </nav>
  );
}
