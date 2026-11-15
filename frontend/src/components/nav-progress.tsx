"use client";

import { usePathname, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

/**
 * A thin bar along the top of the window from the moment an in-app link is clicked until the
 * new page arrives, so a slow server render never looks like a dead click. It listens for
 * clicks on same-origin links (not new-tab or modified clicks, not same-page anchors) and stops
 * when the URL changes.
 */
export function NavProgress() {
  const here = `${usePathname()}?${useSearchParams()}`;
  // The URL the click happened on; once the URL differs, the navigation has landed.
  const [from, setFrom] = useState<string | null>(null);
  const active = from === here;

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey)
        return;
      const link = (e.target as Element | null)?.closest?.("a[href]");
      if (!(link instanceof HTMLAnchorElement) || link.target === "_blank" || link.download) return;
      const url = new URL(link.href, location.href);
      if (url.origin !== location.origin) return;
      const same = url.pathname === location.pathname && url.search === location.search;
      if (same) return;
      setFrom(`${location.pathname}?${new URLSearchParams(location.search)}`);
    };
    document.addEventListener("click", onClick, true);
    return () => document.removeEventListener("click", onClick, true);
  }, []);

  return <div aria-hidden className="nav-progress" data-active={active} />;
}
