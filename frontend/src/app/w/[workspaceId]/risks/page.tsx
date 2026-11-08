import Link from "next/link";

import { ApiErrorNotice } from "@/components/api-error-notice";
import { EmptyState, formatDateTime, PageHeader } from "@/components/page";
import { RiskStatusBadge, SeverityBadge } from "@/components/ui/badge";
import { attempt } from "@/lib/attempt";
import { api } from "@/lib/relay-api";
import { cn } from "@/lib/utils";

const TABS = [
  { value: "active", label: "Open" },
  { value: "accepted", label: "Accepted" },
  { value: "resolved", label: "Resolved" },
] as const;

export default async function RisksPage({
  params,
  searchParams,
}: PageProps<"/w/[workspaceId]/risks">) {
  const [{ workspaceId }, query] = await Promise.all([params, searchParams]);
  const tab = TABS.find((t) => t.value === query.status)?.value ?? "active";
  const base = `/w/${workspaceId}`;

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader title="Continuity risks" />
      <div className="flex flex-col gap-4 p-6">
        <p className="text-muted-foreground max-w-prose text-sm">
          Rule-based checks on the current catalogue. A risk resolves on its own as soon as the gap
          is fixed; until then it can be acknowledged or accepted for a limited time.
        </p>
        <nav aria-label="Risk status" className="flex gap-1 text-sm">
          {TABS.map((t) => (
            <Link
              key={t.value}
              href={t.value === "active" ? `${base}/risks` : `${base}/risks?status=${t.value}`}
              aria-current={tab === t.value ? "page" : undefined}
              className={cn(
                "rounded-md px-2.5 py-1",
                tab === t.value
                  ? "bg-foreground/[0.06] font-medium"
                  : "text-muted-foreground hover:bg-muted",
              )}
            >
              {t.label}
            </Link>
          ))}
        </nav>
        {tab === "resolved" ? (
          <ResolvedList workspaceId={workspaceId} />
        ) : (
          <ActiveList workspaceId={workspaceId} status={tab} />
        )}
      </div>
    </div>
  );
}

async function ActiveList({
  workspaceId,
  status,
}: {
  workspaceId: string;
  status: "active" | "accepted";
}) {
  const risks = await attempt(api.risks(workspaceId, status));
  if (!risks.ok) return <ApiErrorNotice error={risks.error} />;
  if (risks.data.length === 0) {
    return status === "active" ? (
      <EmptyState
        title="No open risks"
        description="Every active responsibility has a primary owner and a backup, and no one person carries several alone."
      />
    ) : (
      <EmptyState
        title="No accepted risks"
        description="Risks accepted for a period appear here until they expire or are fixed."
      />
    );
  }
  return (
    <ul className="divide-y rounded-lg border">
      {risks.data.map((risk) => (
        <li key={risk.key}>
          <Link
            href={`/w/${workspaceId}/risks/${encodeURIComponent(risk.key)}`}
            className="hover:bg-muted/40 flex items-start gap-3 px-4 py-3"
          >
            <SeverityBadge value={risk.severity} />
            <span className="min-w-0 flex-1 text-sm">
              <span className="font-medium">{risk.title}</span>
              <span className="text-muted-foreground mx-1.5">·</span>
              <span>{risk.responsibility?.name ?? risk.person_name}</span>
              <span className="text-muted-foreground block">{risk.explanation}</span>
            </span>
            <span className="flex shrink-0 flex-col items-end gap-1">
              <RiskStatusBadge value={risk.status} />
              {risk.status === "accepted" && risk.accepted_until ? (
                <span className="text-muted-foreground text-xs">
                  until {formatDateTime(risk.accepted_until)}
                </span>
              ) : null}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

async function ResolvedList({ workspaceId }: { workspaceId: string }) {
  const resolved = await attempt(api.resolvedRisks(workspaceId));
  if (!resolved.ok) return <ApiErrorNotice error={resolved.error} />;
  if (resolved.data.length === 0) {
    return (
      <EmptyState
        title="Nothing resolved yet"
        description="Risks move here automatically once the catalogue no longer has the gap."
      />
    );
  }
  return (
    <ul className="divide-y rounded-lg border">
      {resolved.data.map((r) => (
        <li key={r.key} className="flex items-center gap-3 px-4 py-3 text-sm">
          <SeverityBadge value={r.severity} />
          <span className="min-w-0 flex-1">
            <span className="font-medium">{r.title}</span>
            {r.subject ? (
              <>
                <span className="text-muted-foreground mx-1.5">·</span>
                {r.subject}
              </>
            ) : null}
          </span>
          <span className="text-muted-foreground text-xs">
            Resolved {formatDateTime(r.resolved_at)}
          </span>
        </li>
      ))}
    </ul>
  );
}
