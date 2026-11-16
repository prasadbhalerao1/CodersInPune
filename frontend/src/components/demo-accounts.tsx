"use client";

// WHY DEMO ACCOUNTS EXIST: Relay is a real product. Anyone can sign in with their own email
// (WorkOS) and connect their real GitHub, Linear, Notion and Slack accounts; that is the normal
// path and uses exactly the same code. Doing that during judging would be slow, and a fresh
// organisation would not yet show the edge cases (a leaver, stale knowledge, conflicts, blocked
// handovers). So, to give judges the full experience in minutes, we also ship pre-seeded
// sample data and one shared demo account per role. Nothing here is a mock or a shortcut.

import { ArrowRight, Check, ChevronDown, Copy } from "lucide-react";
import { useState } from "react";

import { DEMO_ACCOUNTS, DEMO_PASSWORD } from "@/lib/demo-accounts";
import { cn } from "@/lib/utils";

/**
 * Judge sign-in, visible without a click: the recommended account's credentials and a
 * one-click button, with the other roles one tap away. Each link opens the real sign-in for
 * that account; the shared password is shown with a copy button.
 */
export function DemoAccounts({
  className,
  align = "start",
}: {
  className?: string;
  align?: "start" | "center";
}) {
  const [copied, setCopied] = useState<string | null>(null);
  const [first, ...others] = DEMO_ACCOUNTS;

  async function copy(value: string) {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(value);
      setTimeout(() => setCopied(null), 1500);
    } catch {
      // Clipboard blocked: the value stays visible to copy by hand.
    }
  }

  return (
    <div
      className={cn(
        "bg-card/90 text-card-foreground w-full max-w-sm rounded-xl border p-3 text-left text-sm shadow-sm backdrop-blur",
        align === "center" && "mx-auto",
        className,
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-semibold tracking-wide uppercase">Judges: sign in instantly</p>
        <a
          href={`/sign-in?as=${first.role}`}
          className="bg-primary text-primary-foreground inline-flex shrink-0 items-center gap-1 rounded-lg px-3 py-1.5 text-xs font-semibold hover:opacity-90"
        >
          Sign in as {first.label}
          <ArrowRight className="h-3.5 w-3.5" aria-hidden />
        </a>
      </div>
      <dl className="mt-2 grid grid-cols-[auto_1fr_auto] items-center gap-x-2 gap-y-1 text-xs">
        <dt className="text-muted-foreground">Email</dt>
        <dd className="truncate font-mono">{first.email}</dd>
        <dd>
          <CopyButton value={first.email} label="email" copied={copied} onCopy={copy} />
        </dd>
        <dt className="text-muted-foreground">Password</dt>
        <dd className="truncate font-mono">{DEMO_PASSWORD}</dd>
        <dd>
          <CopyButton value={DEMO_PASSWORD} label="password" copied={copied} onCopy={copy} />
        </dd>
      </dl>
      <details className="group mt-2 border-t pt-2">
        <summary className="text-muted-foreground hover:text-foreground inline-flex cursor-pointer list-none items-center gap-1 text-xs [&::-webkit-details-marker]:hidden">
          {others.length} more roles (same password)
          <ChevronDown
            className="h-3.5 w-3.5 transition-transform group-open:rotate-180"
            aria-hidden
          />
        </summary>
        <ul className="mt-1 space-y-0.5">
          {others.map((a) => (
            <li key={a.role}>
              <a
                href={`/sign-in?as=${a.role}`}
                className="hover:bg-muted block rounded-lg px-2 py-1.5"
              >
                <span className="flex items-baseline justify-between gap-2">
                  <span className="font-medium">{a.label}</span>
                  <span className="text-muted-foreground truncate font-mono text-[11px]">
                    {a.email}
                  </span>
                </span>
                <span className="text-muted-foreground block text-xs">{a.shows}</span>
              </a>
            </li>
          ))}
        </ul>
      </details>
      <p className="text-muted-foreground mt-2 text-[11px] leading-snug">
        A shared sample organisation, so you needn&apos;t connect anything. Relay runs on real
        workspaces: sign up with your own email and connect GitHub, Linear, Notion and Slack.
      </p>
    </div>
  );
}

function CopyButton({
  value,
  label,
  copied,
  onCopy,
}: {
  value: string;
  label: string;
  copied: string | null;
  onCopy: (value: string) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onCopy(value)}
      aria-label={`Copy ${label}`}
      className="hover:bg-muted text-muted-foreground hover:text-foreground inline-flex shrink-0 items-center rounded-md p-1"
    >
      {copied === value ? (
        <Check className="h-3.5 w-3.5" aria-hidden />
      ) : (
        <Copy className="h-3.5 w-3.5" aria-hidden />
      )}
    </button>
  );
}
