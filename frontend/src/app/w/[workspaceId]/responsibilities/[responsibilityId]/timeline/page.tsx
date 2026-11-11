import type { Metadata } from "next";
import Link from "next/link";

import { ApiErrorNotice } from "@/components/api-error-notice";
import { PageHeader } from "@/components/page";
import { attempt } from "@/lib/attempt";
import { api } from "@/lib/relay-api";

import { MemoryReplay } from "./memory-replay";

export const metadata: Metadata = { title: "Memory replay" };

export default async function TimelinePage({
  params,
}: PageProps<"/w/[workspaceId]/responsibilities/[responsibilityId]/timeline">) {
  const { workspaceId, responsibilityId } = await params;
  const [timeline, stored] = await Promise.all([
    attempt(api.timeline(workspaceId, responsibilityId)),
    attempt(api.storedNarrative(workspaceId, responsibilityId)),
  ]);
  if (!timeline.ok) return <ApiErrorNotice error={timeline.error} />;
  const t = timeline.data;
  const base = `/w/${workspaceId}/responsibilities/${responsibilityId}`;
  return (
    <div className="flex flex-1 flex-col">
      <PageHeader
        title={
          <span className="flex items-center gap-2">
            <Link href={base} className="text-muted-foreground hover:text-foreground truncate">
              {t.responsibility_name}
            </Link>
            <span className="text-muted-foreground">/</span>
            <span>Memory replay</span>
          </span>
        }
        description="How this work got to where it is: rebuilt from GitHub, Linear, Notion and Relay every time you open it."
      />
      <MemoryReplay
        workspaceId={workspaceId}
        timeline={t}
        stored={stored.ok && stored.data.state === "ready" ? stored.data : null}
      />
    </div>
  );
}
