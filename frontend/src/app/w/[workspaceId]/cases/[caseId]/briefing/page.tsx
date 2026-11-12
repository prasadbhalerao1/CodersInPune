import Link from "next/link";

import { ApiErrorNotice } from "@/components/api-error-notice";
import { PageHeader } from "@/components/page";
import { attempt } from "@/lib/attempt";
import { api } from "@/lib/relay-api";

import { BriefingSection } from "../collaboration";

/** The return briefing on its own page: linkable, reviewable before cover ends, printable. */
export default async function BriefingPage({
  params,
}: PageProps<"/w/[workspaceId]/cases/[caseId]/briefing">) {
  const { workspaceId, caseId } = await params;
  const briefing = await attempt(api.caseBriefing(workspaceId, caseId));
  if (!briefing.ok) return <ApiErrorNotice error={briefing.error} />;
  const b = briefing.data;
  return (
    <div className="flex flex-1 flex-col">
      <PageHeader
        title={
          <span className="flex items-center gap-2">
            <Link
              href={`/w/${workspaceId}/cases/${caseId}`}
              className="text-muted-foreground hover:text-foreground truncate"
            >
              {b.title}
            </Link>
            <span className="text-muted-foreground">/</span>
            <span>Return briefing</span>
          </span>
        }
      />
      <div className="max-w-4xl p-6">
        {!b.returned ? (
          <p role="status" className="mb-4 rounded-lg border px-4 py-3 text-sm">
            Cover is still running. This is the briefing so far; review it before ending cover.
          </p>
        ) : null}
        <BriefingSection briefing={b} />
      </div>
    </div>
  );
}
