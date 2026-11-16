import { ArrowRight } from "lucide-react";
import Link from "next/link";

import { RelayLines } from "@/components/brand";
import { Avatar } from "@/components/visual";
import type { WorkspaceView } from "@/lib/types";

/** The landing page's atmosphere, so the crystal cards have colour behind them to refract. */
export function WorkspacesBackdrop() {
  return (
    <div aria-hidden className="pointer-events-none absolute inset-0">
      <div
        className="absolute -top-40 right-[-8%] size-[34rem] rounded-full blur-3xl"
        style={{ background: "var(--bloom)" }}
      />
      <div
        className="absolute bottom-[-14rem] left-[-10%] size-[30rem] rounded-full blur-3xl"
        style={{ background: "color-mix(in srgb, var(--peri) 16%, transparent)" }}
      />
      <RelayLines className="absolute top-0 right-0 hidden h-72 w-[46%] opacity-70 md:block" />
    </div>
  );
}

/** The signed-in person's workspaces, or a pointer to the sample one when there are none. */
export function WorkspaceRows({ workspaces }: { workspaces: WorkspaceView[] }) {
  if (workspaces.length === 0) {
    return (
      <div className="glass-clear flex flex-col self-start p-8">
        <span className="text-ac text-[13px] font-medium">Welcome to Relay</span>
        <h2 className="font-heading text-strong mt-2 text-2xl font-bold">Two ways to start</h2>
        <ol className="mt-5 flex flex-col gap-5 text-sm">
          <li>
            <p className="text-strong font-semibold">
              1. Explore the sample (2 minutes, nothing to connect)
            </p>
            <p className="text-fg-soft mt-1 leading-relaxed">
              <em>Northwind Labs (demo)</em> is a team mid-handover: a year of GitHub, Linear and
              Notion history, meetings, risks and an engineer who is leaving. Use{" "}
              <strong>Create sample workspace</strong> on the right. Inside, the banner lets you try
              Relay as any of the eight roles. Recommended for judges.
            </p>
          </li>
          <li>
            <p className="text-strong font-semibold">2. Set up your own organisation</p>
            <ul className="text-fg-soft mt-1 flex list-disc flex-col gap-1 pl-5 leading-relaxed">
              <li>Create a workspace (right): it is private to your team.</li>
              <li>
                Connect GitHub, Linear, Notion or Slack in <strong>Integrations</strong>, all
                read-only, or import a CSV. This is optional: you can start by hand.
              </li>
              <li>
                Add your first responsibility and its owner. The setup checklist then guides you to
                backups, knowledge and your first what-if.
              </li>
            </ul>
          </li>
        </ol>
      </div>
    );
  }
  return (
    <ul className="motion-stagger flex flex-col gap-3" aria-label="Your workspaces">
      {workspaces.map((workspace) => (
        <li key={workspace.id}>
          <Link
            href={`/w/${workspace.id}`}
            className="group glass-clear flex items-center gap-4 px-5 py-4 transition-transform duration-200 hover:-translate-y-0.5"
          >
            <Avatar name={workspace.name} size="lg" className="rounded-xl ring-0" />
            <span className="min-w-0 flex-1">
              <span className="text-strong group-hover:text-ac block truncate font-semibold transition-colors">
                {workspace.name}
              </span>
              <span className="text-fg-mute text-xs">{workspace.role.replace("_", " ")}</span>
            </span>
            <span className="border-line/15 text-fg-mute group-hover:border-ac/50 group-hover:text-ac flex size-8 shrink-0 items-center justify-center rounded-full border transition-colors">
              <ArrowRight
                aria-hidden
                className="size-4 transition-transform group-hover:translate-x-0.5"
              />
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
