"use client";

import { Moon, Sun } from "lucide-react";
import { useEffect, useState, useSyncExternalStore } from "react";

import { cn } from "@/lib/utils";

// The `dark` class on <html> is the single source of truth. Every load starts in light mode (an
// inline script in the root layout makes sure of it before first paint); switching to dark lasts
// until the next load and is deliberately not remembered.

function subscribe(onChange: () => void) {
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["class"] });
  return () => observer.disconnect();
}

const isDark = () => document.documentElement.classList.contains("dark");

/**
 * Sun/moon switch. With `hint`, every load (always light) shows a small pop-up under it:
 * "Prefer dark mode? Click to switch." It closes itself after a few seconds, when the button is
 * used, or with its close button.
 */
export function ThemeToggle({ className, hint = false }: { className?: string; hint?: boolean }) {
  const dark = useSyncExternalStore(subscribe, isDark, () => false);
  const [showHint, setShowHint] = useState(false);

  useEffect(() => {
    if (!hint) return;
    const open = setTimeout(() => setShowHint(true), 1400);
    const close = setTimeout(() => setShowHint(false), 10000);
    return () => {
      clearTimeout(open);
      clearTimeout(close);
    };
  }, [hint]);

  const dismiss = () => setShowHint(false);

  const toggle = () => {
    const next = !dark;
    document.documentElement.classList.toggle("dark", next);
    document.documentElement.style.colorScheme = next ? "dark" : "light";
    dismiss();
  };

  return (
    <span className="relative inline-flex">
      <button
        type="button"
        onClick={toggle}
        aria-label={dark ? "Switch to white mode" : "Switch to dark mode"}
        className={cn(
          "glass-clear text-strong grid size-11 shrink-0 place-items-center !rounded-full transition-transform hover:scale-105",
          className,
        )}
      >
        {dark ? <Sun className="size-4" aria-hidden /> : <Moon className="size-4" aria-hidden />}
      </button>

      {showHint && !dark ? (
        // Outer span places the pop-up (the crystal class sets its own position, so it must
        // not be on the element that is absolutely positioned).
        <span
          role="status"
          className="hero-in absolute top-full left-1/2 z-50 mt-3 w-max max-w-[15rem] -translate-x-1/2"
        >
          <span className="glass-dark text-strong flex items-start gap-2 !rounded-xl px-3 py-2 text-xs leading-snug shadow-lg">
            <span
              aria-hidden
              className="bg-page/90 border-line/25 absolute -top-1 left-1/2 size-2 -translate-x-1/2 rotate-45 border-t border-l"
            />
            <span>
              Prefer dark mode? <span className="text-ac font-medium">Click to switch.</span>
            </span>
            <button
              type="button"
              onClick={dismiss}
              aria-label="Dismiss"
              className="text-fg-mute hover:text-strong -mt-0.5 -mr-1 shrink-0 px-1 text-sm leading-none"
            >
              ×
            </button>
          </span>
        </span>
      ) : null}
    </span>
  );
}
