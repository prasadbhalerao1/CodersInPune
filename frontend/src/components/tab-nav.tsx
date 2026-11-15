"use client";

import Link from "next/link";
import { createContext, use, useState, type ComponentProps, type ReactNode } from "react";

import { cn } from "@/lib/utils";

type Ctx = { active: string; pending: boolean; select: (tab: string) => void };
const TabState = createContext<Ctx>({ active: "", pending: false, select: () => {} });

/**
 * Navigation tabs whose content the server loads: the clicked tab lights up at once and the
 * panel below dims until the new content arrives, so a click never looks ignored.
 */
export function TabNav({
  current,
  children,
  ...props
}: { current: string; children: ReactNode } & ComponentProps<"nav">) {
  const [clicked, setClicked] = useState<{ from: string; to: string } | null>(null);
  // A click only counts while the server still shows the tab it was made from.
  const pending = clicked !== null && clicked.from === current && clicked.to !== current;
  const active = pending ? clicked.to : current;
  return (
    <TabState value={{ active, pending, select: (to) => setClicked({ from: current, to }) }}>
      <nav {...props} data-tab-pending={pending || undefined}>
        {children}
      </nav>
    </TabState>
  );
}

export function TabLink({
  tab,
  className,
  activeClassName,
  inactiveClassName,
  children,
  ...props
}: {
  tab: string;
  activeClassName: string;
  inactiveClassName: string;
} & ComponentProps<typeof Link>) {
  const { active, select } = use(TabState);
  const on = active === tab;
  return (
    <Link
      {...props}
      aria-current={on ? "page" : undefined}
      onClick={(e) => {
        props.onClick?.(e);
        if (!e.metaKey && !e.ctrlKey && !e.shiftKey && e.button === 0) select(tab);
      }}
      className={cn(className, on ? activeClassName : inactiveClassName)}
    >
      {children}
    </Link>
  );
}
