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
  searchParams,
}: PageProps<"/w/[workspaceId]/responsibilities/[responsibilityId]/timeline">) {
  const [{ workspaceId, responsibilityId }, query] = await Promise.all([params, searchParams]);
  // Large histories are read 200 events at a time, newest first.
  const before =
    typeof query.before === "string" && !Number.isNaN(Date.parse(query.before))
      ? query.before
      : undefined;
  const [timeline, stored] = await Promise.all([
    attempt(api.timeline(workspaceId, responsibilityId, undefined, before)),
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
        olderHref={
          t.truncated && t.events.length > 0
            ? `${base}/timeline?before=${encodeURIComponent(t.events[t.events.length - 1].occurred_at)}`
            : null
        }
        latestHref={before ? `${base}/timeline` : null}
        stored={stored.ok && stored.data.state === "ready" ? stored.data : null}
      />
    </div>
  );
}
