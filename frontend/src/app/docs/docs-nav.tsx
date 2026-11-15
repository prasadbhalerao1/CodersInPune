"use client";

import { Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { cn } from "@/lib/utils";

export type NavGroup = { title: string; items: { id: string; title: string }[] };

/**
 * The guide's sidebar: a filter box and the sections, with the one being read highlighted
 * as you scroll (IntersectionObserver, no scroll listeners).
 */
export function DocsNav({ groups }: { groups: NavGroup[] }) {
  const [active, setActive] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const ids = useMemo(() => groups.flatMap((g) => g.items.map((i) => i.id)), [groups]);

  useEffect(() => {
    const seen = new Map<string, boolean>();
    const observer = new IntersectionObserver(
      (entries) => {
        for (const e of entries) seen.set(e.target.id, e.isIntersecting);
        const first = ids.find((id) => seen.get(id));
        if (first) setActive(first);
      },
      { rootMargin: "-80px 0px -60% 0px" },
    );
    for (const id of ids) {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    }
    return () => observer.disconnect();
  }, [ids]);

  const needle = query.trim().toLowerCase();
  const shown = groups
    .map((g) => ({
      ...g,
      items: g.items.filter((i) => !needle || i.title.toLowerCase().includes(needle)),
    }))
    .filter((g) => g.items.length > 0);

  return (
    <nav aria-label="Guide sections" className="flex flex-col gap-6 text-sm">
      <label className="relative">
        <span className="sr-only">Filter the guide</span>
        <Search
          aria-hidden
          className="text-muted-foreground pointer-events-none absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2"
        />
        <input
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            const first = shown[0]?.items[0];
            if (e.key === "Enter" && first) {
              document.getElementById(first.id)?.scrollIntoView({ behavior: "smooth" });
              history.replaceState(null, "", `#${first.id}`);
            }
          }}
          placeholder="Find a metric or feature"
          className="bg-card focus-visible:ring-ring/40 h-9 w-full rounded-md border pr-3 pl-8 text-sm outline-none focus-visible:ring-2"
        />
      </label>
      {shown.length === 0 ? (
        <p className="text-muted-foreground px-1">Nothing matches.</p>
      ) : (
        shown.map((g) => (
          <div key={g.title}>
            <p className="text-muted-foreground mb-2 px-3 text-[11px] font-semibold tracking-[0.08em] uppercase">
              {g.title}
            </p>
            <ul className="border-border flex flex-col border-l">
              {g.items.map((i) => (
                <li key={i.id}>
                  <a
                    href={`#${i.id}`}
                    aria-current={active === i.id ? "location" : undefined}
                    className={cn(
                      "-ml-px block border-l px-3 py-1.5 transition-colors duration-150",
                      active === i.id
                        ? "border-primary text-foreground font-medium"
                        : "text-muted-foreground hover:text-foreground hover:border-foreground/30 border-transparent",
                    )}
                  >
                    {i.title}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        ))
      )}
    </nav>
  );
}
