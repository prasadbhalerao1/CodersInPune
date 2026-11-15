"use client";

import { createContext, use, useState, type ReactNode } from "react";

import { cn } from "@/lib/utils";

const Active = createContext<string>("all");

type Filter = { key: string; label: string; count?: number };

/**
 * Tabs over data the page already loaded: switching is instant (no server round trip) and the
 * URL follows along (`?show=…`) so a reload or shared link opens the same tab.
 */
export function FilterTabs({
  filters,
  initial,
  param = "show",
  label = "Filter",
  children,
}: {
  filters: readonly Filter[];
  initial: string;
  param?: string;
  label?: string;
  children: ReactNode;
}) {
  const [active, setActive] = useState(initial);
  const first = filters[0]?.key;

  function select(key: string) {
    setActive(key);
    const url = new URL(window.location.href);
    if (key === first) url.searchParams.delete(param);
    else url.searchParams.set(param, key);
    window.history.replaceState(null, "", url);
  }

  return (
    <Active value={active}>
      <div role="tablist" aria-label={label} className="flex flex-wrap gap-1 text-sm">
        {filters.map((f) => {
          const on = f.key === active;
          return (
            <button
              key={f.key}
              type="button"
              role="tab"
              aria-selected={on}
              onClick={() => select(f.key)}
              className={cn(
                "rounded-md px-2.5 py-1 transition-colors duration-150 active:scale-[0.97]",
                on ? "bg-foreground/[0.06] font-medium" : "text-muted-foreground hover:bg-muted",
              )}
            >
              {f.label}
              {f.count ? (
                <span className="text-muted-foreground ml-1.5 text-xs tabular-nums">{f.count}</span>
              ) : null}
            </button>
          );
        })}
      </div>
      {children}
    </Active>
  );
}

/** Renders its children only while one of `when` is the active filter. */
export function Filtered({ when, children }: { when: readonly string[]; children: ReactNode }) {
  const active = use(Active);
  return when.includes(active) ? children : null;
}
