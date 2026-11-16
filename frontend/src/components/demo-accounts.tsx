"use client";

import { Check, ChevronDown, Copy } from "lucide-react";
import { useState } from "react";

import { DEMO_ACCOUNTS, DEMO_PASSWORD } from "@/lib/demo-accounts";
import { cn } from "@/lib/utils";

/**
 * "Judging? Sign in as any role": a closed-by-default menu, so the page stays clean. Each
 * entry opens the real sign-in with that account's email filled in; the shared password is
 * shown once, with a copy button.
 */
export function DemoAccounts({
  className,
  align = "start",
}: {
  className?: string;
  align?: "start" | "center";
}) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(DEMO_PASSWORD);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard blocked: the password stays visible to copy by hand.
    }
  }

  return (
    <details className={cn("group relative text-sm", className)}>
      <summary className="text-fg-soft hover:text-strong inline-flex cursor-pointer list-none items-center gap-1 underline-offset-4 hover:underline [&::-webkit-details-marker]:hidden">
        Judging? Sign in as any role
        <ChevronDown
          className="h-3.5 w-3.5 transition-transform group-open:rotate-180"
          aria-hidden
        />
      </summary>
      <div
        className={cn(
          "bg-card text-card-foreground absolute z-30 mt-2 w-[min(22rem,calc(100vw-2rem))] rounded-xl border p-3 text-left shadow-xl",
          align === "center" ? "left-1/2 -translate-x-1/2" : "left-0",
        )}
      >
        <div className="bg-muted/60 flex items-center justify-between gap-2 rounded-lg px-3 py-2 text-xs">
          <span>
            Password for every account: <code className="font-semibold">{DEMO_PASSWORD}</code>
          </span>
          <button
            type="button"
            onClick={copy}
            className="hover:bg-background inline-flex items-center gap-1 rounded-md border px-2 py-1"
          >
            {copied ? (
              <Check className="h-3 w-3" aria-hidden />
            ) : (
              <Copy className="h-3 w-3" aria-hidden />
            )}
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
        <ul className="mt-2 space-y-1">
          {DEMO_ACCOUNTS.map((a, i) => (
            <li key={a.role}>
              <a
                href={`/sign-in?as=${a.role}`}
                className="hover:bg-muted block rounded-lg px-3 py-2"
              >
                <span className="flex items-center gap-2 font-medium">
                  {a.label}
                  {i === 0 ? (
                    <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300">
                      Best for a demo
                    </span>
                  ) : null}
                </span>
                <span className="text-muted-foreground block text-xs">{a.shows}</span>
              </a>
            </li>
          ))}
        </ul>
        <p className="text-muted-foreground mt-2 border-t pt-2 text-xs">
          These open a shared sample organisation so you needn&apos;t connect anything. Relay is
          built for real workspaces: sign up with your own email and connect GitHub, Linear, Notion
          and Slack.
        </p>
      </div>
    </details>
  );
}
