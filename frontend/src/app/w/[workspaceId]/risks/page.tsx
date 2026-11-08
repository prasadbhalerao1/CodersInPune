import Link from "next/link";

import { ApiErrorNotice } from "@/components/api-error-notice";
import { EmptyState, PageHeader } from "@/components/page";
import { SeverityBadge } from "@/components/ui/badge";
import { attempt } from "@/lib/attempt";
import { api } from "@/lib/relay-api";

export default async function RisksPage({ params }: PageProps<"/w/[workspaceId]/risks">) {
  const { workspaceId } = await params;
  const risks = await attempt(api.risks(workspaceId));
  if (!risks.ok) return <ApiErrorNotice error={risks.error} />;
  const base = `/w/${workspaceId}`;

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader title="Continuity risks" />
      <div className="flex flex-col gap-4 p-6">
        <p className="text-muted-foreground max-w-prose text-sm">
          Rule-based checks on the current catalogue. Risks disappear as soon as the underlying gap
          is fixed.
        </p>
        {risks.data.length === 0 ? (
          <EmptyState
            title="No open risks"
            description="Every active responsibility has a primary owner and a backup, and no one person carries several alone."
          />
        ) : (
          <ul className="divide-y rounded-lg border">
            {risks.data.map((risk) => (
              <li key={risk.key}>
                <Link
                  href={`${base}/risks/${encodeURIComponent(risk.key)}`}
                  className="hover:bg-muted/40 flex items-start gap-3 px-4 py-3"
                >
                  <SeverityBadge value={risk.severity} />
                  <span className="min-w-0 flex-1 text-sm">
                    <span className="font-medium">{risk.title}</span>
                    <span className="text-muted-foreground mx-1.5">·</span>
                    <span>{risk.responsibility?.name ?? risk.person_name}</span>
                    <span className="text-muted-foreground block">{risk.explanation}</span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
