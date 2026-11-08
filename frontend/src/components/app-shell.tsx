import type { ReactNode } from "react";
import { Suspense } from "react";

import { UserMenu } from "@/components/user-menu";

// Navigation per Blueprint §H.1. Items are placeholders until their milestone ships;
// they render as disabled so the shell's structure is visible without dead links.
const NAV_GROUPS = [
  { label: "Work", items: ["Home", "My Work", "Cases"] },
  {
    label: "Organisation",
    items: ["Responsibilities", "Knowledge", "Risks", "Insights", "People & Teams"],
  },
] as const;

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-full">
      <aside
        aria-label="Primary"
        className="bg-muted/40 hidden w-60 shrink-0 flex-col border-r md:flex"
      >
        <div className="flex h-14 items-center border-b px-4 font-semibold">Relay</div>
        <nav className="flex flex-1 flex-col gap-6 p-3 text-sm">
          {NAV_GROUPS.map((group) => (
            <div key={group.label}>
              <p className="text-muted-foreground mb-1 px-2 text-xs font-medium uppercase">
                {group.label}
              </p>
              <ul>
                {group.items.map((item) => (
                  <li key={item}>
                    <span
                      aria-disabled="true"
                      className="text-muted-foreground block cursor-not-allowed rounded-md px-2 py-1.5"
                    >
                      {item}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>
        <div className="border-t p-4">
          <Suspense fallback={<span className="text-muted-foreground text-sm">…</span>}>
            <UserMenu />
          </Suspense>
        </div>
      </aside>
      <main className="flex min-w-0 flex-1 flex-col">{children}</main>
    </div>
  );
}
