"use client";

import { PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { useEffect, useSyncExternalStore, type ReactNode } from "react";

// Collapsed or not is a per-browser preference, so it lives in localStorage. Other tabs and the
// keyboard shortcut notify through a custom event.
const KEY = "relay-sidebar-collapsed";
const EVENT = "relay-sidebar";

function subscribe(onChange: () => void) {
  window.addEventListener(EVENT, onChange);
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener(EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}

function read() {
  try {
    return localStorage.getItem(KEY) === "1";
  } catch {
    return false;
  }
}

function setCollapsed(next: boolean) {
  try {
    localStorage.setItem(KEY, next ? "1" : "0");
  } catch {
    // storage blocked: the toggle still works for this page view
  }
  window.dispatchEvent(new Event(EVENT));
}

/**
 * The desktop sidebar: expands to labels or collapses to an icon rail (Ctrl/⌘ + B). Children read
 * the state from the `group/sb` data attribute, so they stay server components.
 */
export function SidebarFrame({ children }: { children: ReactNode }) {
  const collapsed = useSyncExternalStore(subscribe, read, () => false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "b") {
        e.preventDefault();
        setCollapsed(!read());
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const Icon = collapsed ? PanelLeftOpen : PanelLeftClose;
  return (
    <aside
      aria-label="Primary"
      data-collapsed={collapsed}
      className="group/sb bg-sidebar text-sidebar-foreground border-sidebar-border sidebar-frame sticky top-0 z-20 hidden h-dvh shrink-0 flex-col border-r md:flex"
    >
      {children}
      <button
        type="button"
        onClick={() => setCollapsed(!collapsed)}
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        aria-expanded={!collapsed}
        title={`${collapsed ? "Expand" : "Collapse"} sidebar (Ctrl+B)`}
        className="bg-sidebar border-sidebar-border text-muted-foreground hover:text-foreground absolute top-[4.25rem] -right-3 z-10 grid size-6 place-items-center rounded-full border opacity-0 shadow-sm transition-[opacity,color] duration-150 group-hover/sb:opacity-100 focus-visible:opacity-100"
      >
        <Icon className="size-3.5" aria-hidden />
      </button>
    </aside>
  );
}
