import type { Metadata } from "next";
import { ActionForm, inputClass, SubmitButton } from "@/components/action-form";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { EmptyState, formatDateTime, PageHeader, Section } from "@/components/page";
import { Badge, SeverityBadge } from "@/components/ui/badge";
import { attempt } from "@/lib/attempt";
import { api } from "@/lib/relay-api";
import { cn } from "@/lib/utils";

import { DataScope } from "@/components/data-scope";

import { IntegrationsNav } from "../integrations-nav";
import {
  connectLinearAction,
  decideLinearIdentityAction,
  disconnectLinearAction,
  linkProjectAction,
  syncLinearAction,
} from "./actions";

export const metadata: Metadata = { title: "Linear" };

const SYNC: Record<string, { label: string; tone: "neutral" | "muted" | "warning" | "danger" }> = {
  never: { label: "Not synced", tone: "muted" },
  queued: { label: "Sync queued", tone: "neutral" },
  ok: { label: "Synced", tone: "neutral" },
  partial: { label: "Partially synced", tone: "warning" },
  error: { label: "Sync failed", tone: "danger" },
};

export default async function LinearPage({
  params,
  searchParams,
}: PageProps<"/w/[workspaceId]/integrations/linear">) {
  const [{ workspaceId }, query] = await Promise.all([params, searchParams]);
  const linear = await attempt(api.linear(workspaceId));
  if (!linear.ok) return <ApiErrorNotice error={linear.error} />;
  const { configured, connections, projects } = linear.data;
  const connected = connections.length > 0;
  const [identities, signals, responsibilities, people] = connected
    ? await Promise.all([
        attempt(api.linearIdentities(workspaceId)),
        attempt(api.linearSignals(workspaceId)),
        attempt(api.listResponsibilities(workspaceId)),
        attempt(api.listPeople(workspaceId)),
      ])
    : [null, null, null, null];
  const review = identities?.ok
    ? identities.data.filter((i) => i.active && ["suggested", "unmatched"].includes(i.link_status))
    : [];

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader title="Integrations" />
      <IntegrationsNav workspaceId={workspaceId} current="linear" />
      <div className="flex max-w-5xl flex-col gap-8 p-6">
        {query.connected ? (
          <p role="status" className="rounded-lg border px-4 py-3 text-sm">
            Linear connected. The first sync runs in the background; refresh in a moment.
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
          title="Linear"
          description="Read-only: teams, projects, people and issue metadata. Descriptions and comments are never read."
          aside={
            configured ? (
              <ActionForm action={connectLinearAction.bind(null, workspaceId)}>
                <SubmitButton size="sm" pendingLabel="Opening Linear…">
                  {connected ? "Reconnect" : "Connect Linear"}
                </SubmitButton>
              </ActionForm>
            ) : null
          }
        >
          {!configured ? (
            <EmptyState
              title="Linear is not configured"
              description="An administrator needs to set RELAY_LINEAR_CLIENT_ID, RELAY_LINEAR_CLIENT_SECRET and RELAY_INTEGRATION_ENCRYPTION_KEY on the server."
            />
          ) : !connected ? (
            <EmptyState
              title="No Linear workspace connected"
              description="Connect Linear to see which projects and important work lack an accountable owner."
            />
          ) : (
            <ul className="divide-y rounded-lg border">
              {connections.map((c) => (
                <li key={c.id} className="flex flex-wrap items-center gap-3 px-4 py-3 text-sm">
                  <span className="min-w-0 flex-1">
                    <span className="font-medium">{c.organization_name}</span>
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
                    <ActionForm action={syncLinearAction.bind(null, workspaceId, c.id)}>
                      <SubmitButton size="sm" variant="outline" pendingLabel="Queuing…">
                        {c.last_sync_status === "error" ? "Retry sync" : "Sync now"}
                      </SubmitButton>
                    </ActionForm>
                  ) : null}
                  <ActionForm action={disconnectLinearAction.bind(null, workspaceId, c.id)}>
                    <SubmitButton
                      size="sm"
                      variant="ghost"
                      pendingLabel="…"
                      confirm="Disconnect Linear? Relay forgets the access token; synced data stays but stops updating."
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

        {signals?.ok && signals.data.length ? (
          <Section
            title="Signals"
            description="Evidence from Linear. Nothing here changes ownership."
          >
            <ul className="divide-y rounded-lg border">
              {signals.data.map((s) => (
                <li key={s.key} className="flex items-start gap-3 px-4 py-3 text-sm">
                  <SeverityBadge value={s.severity} />
                  <div className="min-w-0 flex-1">
                    <p>
                      <span className="font-medium">{s.title}</span>
                      <span className="text-muted-foreground mx-1.5">·</span>
                      <a
                        href={s.project_url}
                        target="_blank"
                        rel="noreferrer"
                        className="hover:underline"
                      >
                        {s.project}
                      </a>
                    </p>
                    <p className="text-muted-foreground">{s.explanation}</p>
                    <ul className="mt-1 flex flex-wrap gap-x-3 text-xs">
                      {s.evidence.map((e) => (
                        <li key={e.url}>
                          <a
                            href={e.url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-muted-foreground hover:text-foreground hover:underline"
                          >
                            {e.label} ↗
                          </a>
                        </li>
                      ))}
                    </ul>
                  </div>
                </li>
              ))}
            </ul>
          </Section>
        ) : null}

        {projects.length ? (
          <Section
            title="Projects"
            description="Link a project to the responsibility that is accountable for it."
          >
            <ul className="divide-y rounded-lg border">
              {projects.map((p) => (
                <li key={p.id} className="flex flex-wrap items-center gap-3 px-4 py-2.5 text-sm">
                  <span className="min-w-0 flex-1">
                    <a
                      href={p.url}
                      target="_blank"
                      rel="noreferrer"
                      className="font-medium hover:underline"
                    >
                      {p.name}
                    </a>
                    <span className="text-muted-foreground block text-xs">
                      {[
                        p.state,
                        p.lead ? `lead ${p.lead}` : null,
                        `${p.open_issues} open`,
                        `${p.recent_issues} active recently`,
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                    </span>
                  </span>
                  {p.responsibility_id ? (
                    <>
                      <a
                        href={`/w/${workspaceId}/responsibilities/${p.responsibility_id}`}
                        className="text-xs hover:underline"
                      >
                        {p.responsibility_name}
                      </a>
                      <ActionForm
                        action={linkProjectAction.bind(null, workspaceId, p.id, "unlink")}
                      >
                        <SubmitButton size="sm" variant="ghost" pendingLabel="…">
                          Unlink
                        </SubmitButton>
                      </ActionForm>
                    </>
                  ) : (
                    <>
                      {responsibilities?.ok && responsibilities.data.length ? (
                        <ActionForm
                          action={linkProjectAction.bind(null, workspaceId, p.id, "link")}
                          className="flex-row items-center gap-2"
                        >
                          <select
                            name="responsibility_id"
                            defaultValue=""
                            aria-label={`Responsibility for ${p.name}`}
                            className={cn(inputClass, "h-8 w-48")}
                          >
                            <option value="">Link to…</option>
                            {responsibilities.data.map((r) => (
                              <option key={r.id} value={r.id}>
                                {r.name}
                              </option>
                            ))}
                          </select>
                          <SubmitButton size="sm" variant="ghost">
                            Link
                          </SubmitButton>
                        </ActionForm>
                      ) : null}
                      <ActionForm
                        action={linkProjectAction.bind(null, workspaceId, p.id, "create")}
                      >
                        <SubmitButton size="sm" variant="outline">
                          New responsibility
                        </SubmitButton>
                      </ActionForm>
                    </>
                  )}
                </li>
              ))}
            </ul>
          </Section>
        ) : null}

        {review.length && people?.ok ? (
          <Section
            title="People to review"
            description="Matches are suggestions; nothing is linked until you confirm."
          >
            <ul className="divide-y rounded-lg border">
              {review.map((i) => (
                <li key={i.id} className="flex flex-wrap items-center gap-3 px-4 py-2.5 text-sm">
                  <span className="min-w-0 flex-1">
                    <span className="font-medium">{i.name}</span>
                    {i.link_status === "suggested" ? (
                      <Badge tone="warning" className="ml-2">
                        Suggested
                      </Badge>
                    ) : null}
                    <span className="text-muted-foreground block text-xs">
                      {[
                        i.email,
                        i.suggested_person
                          ? `Possibly ${i.suggested_person.name}: ${i.match_reason}`
                          : i.match_reason,
                        i.recent_issues ? `${i.recent_issues} recent issues` : null,
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                    </span>
                  </span>
                  <ActionForm
                    action={decideLinearIdentityAction.bind(null, workspaceId, i.id, "link")}
                    className="flex-row items-center gap-2"
                  >
                    <select
                      name="person_id"
                      defaultValue={i.suggested_person?.id ?? ""}
                      aria-label={`Person for ${i.name}`}
                      className={cn(inputClass, "h-8 w-44")}
                    >
                      <option value="">Choose person…</option>
                      {people.data.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.display_name}
                        </option>
                      ))}
                    </select>
                    <SubmitButton size="sm" variant={i.suggested_person ? "default" : "outline"}>
                      {i.suggested_person ? "Confirm" : "Link"}
                    </SubmitButton>
                  </ActionForm>
                  <ActionForm
                    action={decideLinearIdentityAction.bind(null, workspaceId, i.id, "dismiss")}
                  >
                    <SubmitButton size="sm" variant="ghost" pendingLabel="…">
                      Not ours
                    </SubmitButton>
                  </ActionForm>
                </li>
              ))}
            </ul>
          </Section>
        ) : null}
        <DataScope
          reads={[
            "Teams, projects and people",
            "Issue metadata: identifier, title, state, priority, assignee, dates",
          ]}
          never={["Issue descriptions or comments", "Nothing is written to Linear"]}
        />
      </div>
    </div>
  );
}
