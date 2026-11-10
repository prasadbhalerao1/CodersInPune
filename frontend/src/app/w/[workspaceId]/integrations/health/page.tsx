import type { Metadata } from "next";

import { ActionForm, SubmitButton } from "@/components/action-form";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { EmptyState, formatDateTime, PageHeader } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { attempt } from "@/lib/attempt";
import { api } from "@/lib/relay-api";
import type { ConnectorHealth } from "@/lib/types";
import { cn } from "@/lib/utils";

import { setConnectorPausedAction, syncConnectorAction } from "../actions";
import { IntegrationsNav } from "../integrations-nav";

export const metadata: Metadata = { title: "Integration health" };

const HEALTH: Record<
  ConnectorHealth,
  { label: string; tone: "neutral" | "muted" | "warning" | "danger" }
> = {
  healthy: { label: "Healthy", tone: "neutral" },
  stale: { label: "Stale", tone: "warning" },
  partial: { label: "Partial", tone: "warning" },
  attention_required: { label: "Needs attention", tone: "danger" },
  rate_limited: { label: "Rate limited", tone: "warning" },
  permission_changed: { label: "Permission changed", tone: "danger" },
  paused: { label: "Paused", tone: "muted" },
  revoked: { label: "Revoked", tone: "danger" },
  failed: { label: "Failing", tone: "danger" },
};
const PROVIDER = { github: "GitHub", linear: "Linear", notion: "Notion" } as const;

export default async function HealthPage({
  params,
}: PageProps<"/w/[workspaceId]/integrations/health">) {
  const { workspaceId } = await params;
  const connectors = await attempt(api.connectorHealth(workspaceId));
  if (!connectors.ok) return <ApiErrorNotice error={connectors.error} />;

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader title="Integrations" />
      <IntegrationsNav workspaceId={workspaceId} current="health" />
      <div className="flex max-w-5xl flex-col gap-6 p-6">
        <p className="text-muted-foreground max-w-2xl text-sm">
          Whether each connected tool is current. Relay never shows data from a source as current
          when its last sync failed or access changed; pages that use it say so.
        </p>
        {connectors.data.length === 0 ? (
          <EmptyState
            title="Nothing connected"
            description="Connect GitHub, Linear or Notion from their tabs to see their health here."
          />
        ) : (
          <ul className="flex flex-col gap-4">
            {connectors.data.map((c) => (
              <li key={c.ref} className="rounded-lg border">
                <div className="flex flex-wrap items-center gap-3 border-b px-4 py-3">
                  <span className="font-medium">
                    {PROVIDER[c.provider]} · {c.name}
                  </span>
                  <Badge tone={HEALTH[c.health].tone}>{HEALTH[c.health].label}</Badge>
                  <span className="flex-1" />
                  {c.health !== "revoked" ? (
                    <>
                      {c.health !== "paused" ? (
                        <ActionForm
                          action={syncConnectorAction.bind(null, workspaceId, c.provider, c.ref)}
                        >
                          <SubmitButton size="sm" variant="outline" pendingLabel="Queued…">
                            Sync now
                          </SubmitButton>
                        </ActionForm>
                      ) : null}
                      <ActionForm
                        action={setConnectorPausedAction.bind(
                          null,
                          workspaceId,
                          c.provider,
                          c.ref,
                          c.health !== "paused",
                        )}
                      >
                        <SubmitButton
                          size="sm"
                          variant="ghost"
                          pendingLabel="…"
                          confirm={
                            c.health !== "paused"
                              ? "Pause syncing? Data and credentials are kept; nothing new is read."
                              : undefined
                          }
                        >
                          {c.health === "paused" ? "Resume" : "Pause"}
                        </SubmitButton>
                      </ActionForm>
                    </>
                  ) : null}
                </div>
                <div className="flex flex-col gap-3 px-4 py-3 text-sm">
                  <p className={cn(c.health !== "healthy" && "font-medium")}>{c.advice}</p>
                  <dl className="text-muted-foreground grid grid-cols-2 gap-2 text-xs sm:grid-cols-3">
                    <div>
                      <dt>Last sync</dt>
                      <dd className="text-foreground">
                        {c.last_synced_at ? formatDateTime(c.last_synced_at) : "Never"}
                      </dd>
                    </div>
                    <div>
                      <dt>Last success</dt>
                      <dd className="text-foreground">
                        {c.last_success_at ? formatDateTime(c.last_success_at) : "—"}
                      </dd>
                    </div>
                    <div>
                      <dt>Failure rate (recent runs)</dt>
                      <dd className="text-foreground tabular-nums">
                        {c.failure_rate === null
                          ? "No history yet"
                          : `${Math.round(c.failure_rate * 100)}%`}
                      </dd>
                    </div>
                  </dl>
                  {c.runs.length ? (
                    <details>
                      <summary className="text-muted-foreground hover:text-foreground cursor-pointer text-xs">
                        Sync history ({c.runs.length})
                      </summary>
                      <ol className="mt-2 flex flex-col gap-1 text-xs">
                        {c.runs.map((r, i) => (
                          <li key={i} className="flex flex-wrap gap-2">
                            <span className="w-16 font-medium">{r.status}</span>
                            <span className="text-muted-foreground">
                              {formatDateTime(r.finished_at)}
                            </span>
                            <span className="text-muted-foreground tabular-nums">
                              {r.duration_ms} ms
                            </span>
                            {r.error ? (
                              <span className="text-red-700 dark:text-red-300">{r.error}</span>
                            ) : null}
                          </li>
                        ))}
                      </ol>
                    </details>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
