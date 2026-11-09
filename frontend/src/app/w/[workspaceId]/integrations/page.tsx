import Link from "next/link";

import { ActionForm, SubmitButton } from "@/components/action-form";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { EmptyState, formatDateTime, PageHeader, Section } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { attempt } from "@/lib/attempt";
import { api } from "@/lib/relay-api";
import type { InstallationView } from "@/lib/types";

import { GitHubTabs } from "./github/tabs";
import { IntegrationsNav } from "./integrations-nav";
import {
  connectGitHubAction,
  disconnectInstallationAction,
  setRepositorySelectedAction,
  syncInstallationAction,
} from "./actions";

const SYNC_LABEL: Record<
  InstallationView["last_sync_status"],
  { label: string; tone: "neutral" | "muted" | "warning" | "danger" }
> = {
  never: { label: "Not synced", tone: "muted" },
  queued: { label: "Sync queued", tone: "neutral" },
  ok: { label: "Synced", tone: "neutral" },
  partial: { label: "Partially synced", tone: "warning" },
  error: { label: "Sync failed", tone: "danger" },
};

export default async function IntegrationsPage({
  params,
  searchParams,
}: PageProps<"/w/[workspaceId]/integrations">) {
  const [{ workspaceId }, query] = await Promise.all([params, searchParams]);
  const github = await attempt(api.github(workspaceId));
  if (!github.ok) return <ApiErrorNotice error={github.error} />;
  const { configured, installations, repositories, open_suggestions } = github.data;
  const connected = installations.filter((i) => i.status !== "disconnected");
  const base = `/w/${workspaceId}/integrations`;
  const [review, signals] = connected.length
    ? await Promise.all([
        attempt(api.githubIdentities(workspaceId, "review")),
        attempt(api.githubSignals(workspaceId)),
      ])
    : [null, null];

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader title="Integrations" />
      <IntegrationsNav workspaceId={workspaceId} current="github" />
      {connected.length ? (
        <GitHubTabs
          workspaceId={workspaceId}
          current="overview"
          counts={{
            suggestions: open_suggestions,
            identities: review?.ok ? review.data.length : 0,
            signals: signals?.ok ? signals.data.length : 0,
          }}
        />
      ) : null}
      <div className="flex max-w-5xl flex-col gap-8 p-6">
        {query.connected ? (
          <p role="status" className="rounded-lg border px-4 py-3 text-sm">
            GitHub connected. The first sync runs in the background; refresh in a moment.
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
          title="GitHub"
          description="Read-only: repository metadata, CODEOWNERS, catalog-info.yaml and maintainers. Source code is never read."
          aside={
            configured ? (
              <ActionForm action={connectGitHubAction.bind(null, workspaceId)}>
                <SubmitButton size="sm" pendingLabel="Opening GitHub…">
                  {connected.length ? "Add organisation" : "Connect GitHub"}
                </SubmitButton>
              </ActionForm>
            ) : null
          }
        >
          {!configured ? (
            <EmptyState
              title="GitHub App not configured"
              description="An administrator needs to set the RELAY_GITHUB_* server settings before GitHub can be connected."
            />
          ) : connected.length === 0 ? (
            <EmptyState
              title="No GitHub organisations connected"
              description="Connect an organisation to suggest owners from CODEOWNERS, Backstage catalog files and repository maintainers."
            />
          ) : (
            <ul className="divide-y rounded-lg border">
              {connected.map((i) => (
                <li key={i.id} className="flex flex-wrap items-center gap-3 px-4 py-3 text-sm">
                  <span className="min-w-0 flex-1">
                    <span className="font-medium">{i.account_login}</span>
                    <span className="text-muted-foreground ml-2 text-xs">{i.account_type}</span>
                    <span className="text-muted-foreground block text-xs">
                      {i.last_synced_at
                        ? `Last synced ${formatDateTime(i.last_synced_at)}`
                        : "Never synced"}
                      {" · webhooks + 6-hourly reconciliation"}
                    </span>
                  </span>
                  {i.status === "revoked" ? (
                    <Badge tone="danger">Access revoked</Badge>
                  ) : (
                    <Badge tone={SYNC_LABEL[i.last_sync_status].tone}>
                      {SYNC_LABEL[i.last_sync_status].label}
                    </Badge>
                  )}
                  <ActionForm action={syncInstallationAction.bind(null, workspaceId, i.id)}>
                    <SubmitButton size="sm" variant="outline" pendingLabel="Queuing…">
                      {i.last_sync_status === "error" || i.status === "revoked"
                        ? "Retry sync"
                        : "Sync now"}
                    </SubmitButton>
                  </ActionForm>
                  <ActionForm action={disconnectInstallationAction.bind(null, workspaceId, i.id)}>
                    <SubmitButton size="sm" variant="ghost" pendingLabel="…">
                      Disconnect
                    </SubmitButton>
                  </ActionForm>
                  {i.last_sync_error ? (
                    <p
                      role="status"
                      className="w-full rounded-md border border-amber-600/20 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:bg-amber-950/30 dark:text-amber-200"
                    >
                      {i.last_sync_error}
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </Section>

        {repositories.length > 0 ? (
          <Section
            title="Repositories"
            description="Only selected repositories are read during sync."
            aside={
              <Link
                href={`${base}/github/suggestions`}
                className={buttonVariants({
                  size: "sm",
                  variant: open_suggestions ? "default" : "outline",
                })}
              >
                Review suggestions{open_suggestions ? ` (${open_suggestions})` : ""}
              </Link>
            }
          >
            <ul className="divide-y rounded-lg border">
              {repositories.map((r) => (
                <li key={r.id} className="flex flex-wrap items-center gap-3 px-4 py-2.5 text-sm">
                  <a
                    href={r.html_url}
                    target="_blank"
                    rel="noreferrer"
                    className="min-w-0 flex-1 truncate font-medium hover:underline"
                  >
                    {r.full_name}
                  </a>
                  {r.private ? <Badge tone="muted">Private</Badge> : null}
                  {r.archived ? <Badge tone="muted">Archived</Badge> : null}
                  {!r.accessible ? <Badge tone="warning">No access</Badge> : null}
                  {r.sync_error && r.accessible ? (
                    <Badge tone="warning" className="max-w-56 truncate">
                      {r.sync_error}
                    </Badge>
                  ) : null}
                  {r.responsibility_id ? (
                    <Link
                      href={`/w/${workspaceId}/responsibilities/${r.responsibility_id}`}
                      className="text-muted-foreground text-xs hover:underline"
                    >
                      Responsibility
                    </Link>
                  ) : null}
                  <ActionForm
                    action={setRepositorySelectedAction.bind(null, workspaceId, r.id, !r.selected)}
                  >
                    <SubmitButton size="sm" variant="ghost" pendingLabel="…">
                      {r.selected ? "Exclude" : "Include"}
                    </SubmitButton>
                  </ActionForm>
                </li>
              ))}
            </ul>
          </Section>
        ) : null}
      </div>
    </div>
  );
}
