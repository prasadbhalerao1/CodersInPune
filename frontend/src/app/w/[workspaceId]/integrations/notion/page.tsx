import Link from "next/link";

import { ActionForm, inputClass, SubmitButton } from "@/components/action-form";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { EmptyState, formatDateTime, PageHeader, Section } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { attempt } from "@/lib/attempt";
import { api } from "@/lib/relay-api";
import type { NotionSourceView, ResponsibilitySummary } from "@/lib/types";
import { cn } from "@/lib/utils";

import { IntegrationsNav } from "../integrations-nav";
import {
  connectNotionAction,
  disconnectNotionAction,
  mapNotionSourceAction,
  syncNotionAction,
} from "./actions";

const SYNC: Record<string, { label: string; tone: "neutral" | "muted" | "warning" | "danger" }> = {
  never: { label: "Not synced", tone: "muted" },
  queued: { label: "Sync queued", tone: "neutral" },
  ok: { label: "Synced", tone: "neutral" },
  partial: { label: "Partially synced", tone: "warning" },
  error: { label: "Sync failed", tone: "danger" },
};

export default async function NotionPage({
  params,
  searchParams,
}: PageProps<"/w/[workspaceId]/integrations/notion">) {
  const [{ workspaceId }, query] = await Promise.all([params, searchParams]);
  const [notion, responsibilities] = await Promise.all([
    attempt(api.notion(workspaceId)),
    attempt(api.listResponsibilities(workspaceId)),
  ]);
  if (!notion.ok) return <ApiErrorNotice error={notion.error} />;
  const { configured, connections, sources } = notion.data;
  const connected = connections.length > 0;
  const options = responsibilities.ok ? responsibilities.data : [];
  const mapped = sources.filter((s) => s.responsibility_id);
  const unmapped = sources.filter((s) => !s.responsibility_id && !s.removed);

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader title="Integrations" />
      <IntegrationsNav workspaceId={workspaceId} current="notion" />
      <div className="flex max-w-5xl flex-col gap-8 p-6">
        {query.connected ? (
          <p role="status" className="rounded-lg border px-4 py-3 text-sm">
            Notion connected. Shared pages appear below after the first sync; refresh in a moment.
          </p>
        ) : null}
        {typeof query.error === "string" ? (
          <p
            role="alert"
            className="rounded-lg border border-red-600/20 bg-red-50 px-4 py-3 text-sm text-red-800 dark:bg-red-950/30 dark:text-red-300"
          >
            {query.error}
          </p>
        ) : null}

        <Section
          title="Notion"
          description="Read-only. Relay imports only the pages you map, keeps the Notion link, and flags changed pages for review."
          aside={
            configured ? (
              <ActionForm action={connectNotionAction.bind(null, workspaceId)}>
                <SubmitButton size="sm" pendingLabel="Opening Notion…">
                  {connected ? "Share more pages" : "Connect Notion"}
                </SubmitButton>
              </ActionForm>
            ) : null
          }
        >
          {!configured ? (
            <EmptyState
              title="Notion is not configured"
              description="An administrator needs to set RELAY_NOTION_CLIENT_ID, RELAY_NOTION_CLIENT_SECRET and RELAY_INTEGRATION_ENCRYPTION_KEY on the server."
            />
          ) : !connected ? (
            <EmptyState
              title="No Notion workspace connected"
              description="Connect Notion and choose the runbooks and procedures Relay should keep with each responsibility."
            />
          ) : (
            <ul className="divide-y rounded-lg border">
              {connections.map((c) => (
                <li key={c.id} className="flex flex-wrap items-center gap-3 px-4 py-3 text-sm">
                  <span className="min-w-0 flex-1">
                    <span className="font-medium">{c.workspace_name}</span>
                    <span className="text-muted-foreground block text-xs">
                      {c.last_synced_at
                        ? `Last synced ${formatDateTime(c.last_synced_at)}`
                        : "Never synced"}
                      {c.next_reconcile_at
                        ? ` · next automatic sync ${formatDateTime(c.next_reconcile_at)}`
                        : ""}
                    </span>
                  </span>
                  {c.status === "revoked" ? (
                    <Badge tone="danger">Access revoked</Badge>
                  ) : (
                    <Badge tone={SYNC[c.last_sync_status].tone}>
                      {SYNC[c.last_sync_status].label}
                    </Badge>
                  )}
                  {c.status === "active" ? (
                    <ActionForm action={syncNotionAction.bind(null, workspaceId, c.id)}>
                      <SubmitButton size="sm" variant="outline" pendingLabel="Queuing…">
                        {c.last_sync_status === "error" ? "Retry sync" : "Sync now"}
                      </SubmitButton>
                    </ActionForm>
                  ) : null}
                  <ActionForm action={disconnectNotionAction.bind(null, workspaceId, c.id)}>
                    <SubmitButton
                      size="sm"
                      variant="ghost"
                      pendingLabel="…"
                      confirm="Disconnect Notion? Relay forgets the access token; imported knowledge stays but stops updating."
                    >
                      Disconnect
                    </SubmitButton>
                  </ActionForm>
                  {c.last_sync_error ? (
                    <p
                      role="status"
                      className="w-full rounded-md border border-amber-600/20 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:bg-amber-950/30 dark:text-amber-200"
                    >
                      {c.last_sync_error}
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </Section>

        {mapped.length ? (
          <Section
            title="Imported into Knowledge"
            description="Each page becomes knowledge on its responsibility. Edits happen in Notion."
            aside={
              <Link
                href={`/w/${workspaceId}/knowledge`}
                className="text-muted-foreground hover:text-foreground text-sm hover:underline"
              >
                Open Knowledge →
              </Link>
            }
          >
            <ul className="divide-y rounded-lg border">
              {mapped.map((s) => (
                <li key={s.id} className="flex flex-wrap items-center gap-3 px-4 py-2.5 text-sm">
                  <SourceTitle source={s} />
                  <span className="text-muted-foreground text-xs">
                    {s.responsibility_id ? (
                      <Link
                        href={`/w/${workspaceId}/responsibilities/${s.responsibility_id}`}
                        className="hover:text-foreground hover:underline"
                      >
                        {s.responsibility_name ?? "Responsibility"}
                      </Link>
                    ) : null}
                    {" · "}
                    {s.visibility === "managers" ? "managers only" : "whole workspace"}
                  </span>
                  <ActionForm action={mapNotionSourceAction.bind(null, workspaceId, s.id, true)}>
                    <SubmitButton
                      size="sm"
                      variant="ghost"
                      pendingLabel="…"
                      confirm="Stop importing this source? Its pages are withdrawn from Knowledge."
                    >
                      Stop importing
                    </SubmitButton>
                  </ActionForm>
                </li>
              ))}
            </ul>
          </Section>
        ) : null}

        {connected ? (
          <Section
            title="Shared with Relay"
            description="Nothing is imported until you choose where it belongs and who can see it."
          >
            {unmapped.length === 0 ? (
              <EmptyState
                title={sources.length ? "Everything shared is mapped" : "Nothing shared yet"}
                description="Use “Share more pages” to pick pages or databases in Notion."
              />
            ) : (
              <ul className="divide-y rounded-lg border">
                {unmapped.map((s) => (
                  <li key={s.id} className="flex flex-wrap items-center gap-3 px-4 py-2.5 text-sm">
                    <SourceTitle source={s} />
                    <MapForm workspaceId={workspaceId} source={s} options={options} />
                  </li>
                ))}
              </ul>
            )}
          </Section>
        ) : null}
      </div>
    </div>
  );
}

function SourceTitle({ source: s }: { source: NotionSourceView }) {
  return (
    <span className="min-w-0 flex-1">
      <a href={s.url} target="_blank" rel="noreferrer" className="font-medium hover:underline">
        {s.title} ↗
      </a>
      {s.kind === "database" ? (
        <Badge tone="muted" className="ml-2">
          Database
        </Badge>
      ) : null}
      {s.removed ? (
        <Badge tone="warning" className="ml-2">
          No longer shared
        </Badge>
      ) : null}
      <span className="text-muted-foreground block text-xs">
        {[
          s.imported_pages ? `${s.imported_pages} imported` : null,
          s.withdrawn_pages ? `${s.withdrawn_pages} withdrawn` : null,
          s.last_edited_at ? `edited in Notion ${formatDateTime(s.last_edited_at)}` : null,
        ]
          .filter(Boolean)
          .join(" · ")}
      </span>
    </span>
  );
}

function MapForm({
  workspaceId,
  source,
  options,
}: {
  workspaceId: string;
  source: NotionSourceView;
  options: ResponsibilitySummary[];
}) {
  if (!options.length) {
    return (
      <Link
        href={`/w/${workspaceId}/responsibilities`}
        className="text-muted-foreground hover:text-foreground text-xs hover:underline"
      >
        Create a responsibility first
      </Link>
    );
  }
  return (
    <ActionForm
      action={mapNotionSourceAction.bind(null, workspaceId, source.id, false)}
      className="flex-row flex-wrap items-center gap-2"
    >
      <select
        name="responsibility_id"
        defaultValue=""
        aria-label={`Responsibility for ${source.title}`}
        className={cn(inputClass, "h-8 w-48")}
      >
        <option value="">Responsibility…</option>
        {options.map((r) => (
          <option key={r.id} value={r.id}>
            {r.name}
          </option>
        ))}
      </select>
      <select
        name="visibility"
        defaultValue=""
        aria-label={`Who can see ${source.title}`}
        className={cn(inputClass, "h-8 w-40")}
      >
        <option value="">Visible to…</option>
        <option value="workspace">Whole workspace</option>
        <option value="managers">Managers only</option>
      </select>
      <SubmitButton size="sm" variant="outline">
        Import
      </SubmitButton>
    </ActionForm>
  );
}
