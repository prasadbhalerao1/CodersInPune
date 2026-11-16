"use client";

import { FlaskConical, UserRound, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useState, useTransition } from "react";

import { switchDemoRoleAction } from "@/app/w/[workspaceId]/demo-actions";
import type { DemoRoleView } from "@/lib/types";
import { cn } from "@/lib/utils";

// Who holds each role in the Northwind sample, so a role is a person doing a job.
const PERSONA: Record<string, string> = {
  owner: "you",
  admin: "Maya Chen",
  continuity_manager: "Tom Okafor",
  knowledge_steward: "Ines Duarte",
  team_manager: "Dev Patel",
  member: "Priya Nair",
  auditor: "Riya Desai",
  guest: "Kai Nakamura",
};

const label = (role: string) => role.replace("_", " ").replace(/^./, (c) => c.toUpperCase());

/**
 * Shown only in sample workspaces: says this is sample data (no tools to connect), and lets
 * the person who created it try Relay as any role, then switch back.
 */
export function SampleBanner({ workspaceId, view }: { workspaceId: string; view: DemoRoleView }) {
  const [hidden, setHidden] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, start] = useTransition();
  const key = `relay:sample-banner:${workspaceId}`;

  useEffect(() => {
    try {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      if (localStorage.getItem(key) === "hidden") setHidden(true);
    } catch {
      // storage blocked: keep the banner visible
    }
  }, [key]);

  const trying = view.role !== "owner" && view.can_switch;
  const current = view.roles.find((r) => r.role === view.role);

  function choose(role: string) {
    setError(null);
    start(async () => {
      const result = await switchDemoRoleAction(workspaceId, role);
      if (result.error) setError(result.error);
    });
  }

  if (hidden && !trying) return null;
  return (
    <div
      role="region"
      aria-label="Sample workspace"
      className={cn(
        "border-b px-4 py-2 text-sm",
        trying
          ? "border-amber-600/25 bg-amber-50 text-amber-950 dark:bg-amber-950/30 dark:text-amber-100"
          : "bg-primary/[0.06]",
      )}
    >
      <div className="mx-auto flex max-w-[105rem] flex-wrap items-center gap-x-4 gap-y-2">
        {trying ? (
          <p className="flex min-w-0 flex-1 items-center gap-2">
            <UserRound aria-hidden className="size-4 shrink-0" />
            <span>
              You&apos;re seeing Relay as <strong>{label(view.role)}</strong>
              {PERSONA[view.role] ? ` (like ${PERSONA[view.role]})` : ""}: {current?.purpose}
            </span>
          </p>
        ) : (
          <p className="flex min-w-0 flex-1 items-center gap-2">
            <FlaskConical aria-hidden className="text-primary size-4 shrink-0" />
            <span>
              <strong>Sample organisation.</strong> A year of GitHub, Linear and Notion history is
              already here, so you can try everything without connecting your tools. Relay itself
              runs on your real tools: create a workspace and connect GitHub, Linear, Notion and
              Slack in Integrations.{" "}
              <Link href="/docs" className="underline underline-offset-2">
                How it works
              </Link>
            </span>
          </p>
        )}
        {view.can_switch ? (
          <label className="flex items-center gap-2 text-xs font-medium">
            Try Relay as
            <select
              value={view.role}
              disabled={pending}
              onChange={(e) => choose(e.target.value)}
              className="bg-background h-8 rounded-md border px-2 text-sm"
            >
              {view.roles.map((r) => (
                <option key={r.role} value={r.role} title={r.purpose}>
                  {label(r.role)}
                  {PERSONA[r.role] && r.role !== "owner" ? ` · ${PERSONA[r.role]}` : ""}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        {trying ? (
          <button
            type="button"
            disabled={pending}
            onClick={() => choose("owner")}
            className="rounded-md border border-current/30 px-2.5 py-1 text-xs font-medium"
          >
            Switch back to Owner
          </button>
        ) : (
          <button
            type="button"
            aria-label="Hide this note"
            onClick={() => {
              setHidden(true);
              try {
                localStorage.setItem(key, "hidden");
              } catch {
                // fine: hidden for this visit only
              }
            }}
            className="text-muted-foreground hover:text-foreground"
          >
            <X aria-hidden className="size-4" />
          </button>
        )}
        {pending ? <span className="text-xs">Switching…</span> : null}
        {error ? (
          <span role="alert" className="text-xs">
            {error}
          </span>
        ) : null}
      </div>
    </div>
  );
}
