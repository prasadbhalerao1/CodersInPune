import type { Metadata } from "next";

import { ActionForm, inputClass, SubmitButton } from "@/components/action-form";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { formatDateTime, PageHeader, Section } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { attempt } from "@/lib/attempt";
import { api } from "@/lib/relay-api";

import { IntegrationsNav } from "../integrations-nav";
import { connectSlackAction, disconnectSlackAction } from "./actions";

export const metadata: Metadata = { title: "Slack" };

const STEPS = [
  "In Slack, open api.slack.com/apps, create an app from scratch for your workspace.",
  "Under Incoming Webhooks, switch them on and choose Add New Webhook to Workspace.",
  "Pick the channel for handover updates, allow it, and copy the webhook URL.",
  "Paste it below. Relay sends a test message before saving it.",
];

export default async function SlackPage({
  params,
}: PageProps<"/w/[workspaceId]/integrations/slack">) {
  const { workspaceId } = await params;
  const status = await attempt(api.slack(workspaceId));
  if (!status.ok) return <ApiErrorNotice error={status.error} />;
  const s = status.data;

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader title="Integrations" />
      <IntegrationsNav workspaceId={workspaceId} current="slack" />
      <div className="flex w-full max-w-3xl flex-col gap-8 p-6">
        <Section
          title="Slack"
          description="Write-only: Relay posts to one channel only when someone presses “Post to Slack” on a meeting. It never reads Slack messages and never posts on its own."
          aside={
            s.connected ? (
              <Badge>Connected to #{s.channel}</Badge>
            ) : (
              <Badge tone="muted">Not connected</Badge>
            )
          }
        >
          {s.connected ? (
            <div className="flex flex-col gap-3 rounded-lg border p-4 text-sm">
              <p>
                Posting to <strong>#{s.channel}</strong>
                {s.connected_at ? ` since ${formatDateTime(s.connected_at)}` : ""}.
                {s.last_posted_at
                  ? ` Last post ${formatDateTime(s.last_posted_at)}.`
                  : " Nothing posted yet."}
              </p>
              {s.last_error ? (
                <p role="alert" className="text-amber-700 dark:text-amber-300">
                  The last post failed: {s.last_error}. Reconnect with a new webhook if the channel
                  or app changed.
                </p>
              ) : null}
              {s.can_manage ? (
                <ActionForm action={disconnectSlackAction.bind(null, workspaceId)}>
                  <SubmitButton size="sm" variant="outline" pendingLabel="Disconnecting…">
                    Disconnect Slack
                  </SubmitButton>
                </ActionForm>
              ) : null}
            </div>
          ) : null}
          {s.can_manage && s.available ? (
            <div className="flex flex-col gap-4">
              <ol className="text-muted-foreground list-decimal space-y-1 pl-5 text-sm">
                {STEPS.map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ol>
              <ActionForm
                action={connectSlackAction.bind(null, workspaceId)}
                className="flex flex-col gap-3"
              >
                <label className="flex flex-col gap-1.5 text-sm font-medium">
                  Webhook URL
                  <input
                    name="webhook_url"
                    type="password"
                    required
                    autoComplete="off"
                    placeholder="https://hooks.slack.com/services/…"
                    className={inputClass}
                  />
                </label>
                <label className="flex flex-col gap-1.5 text-sm font-medium">
                  Channel name (for display)
                  <input
                    name="channel"
                    required
                    maxLength={80}
                    placeholder="#handovers"
                    className={inputClass}
                  />
                </label>
                <SubmitButton pendingLabel="Sending a test message…">
                  {s.connected ? "Replace webhook" : "Connect Slack"}
                </SubmitButton>
              </ActionForm>
              <p className="text-muted-foreground text-xs">
                The URL is encrypted at rest and never shown again. Disconnecting deletes it.
              </p>
            </div>
          ) : !s.can_manage ? (
            <p className="text-muted-foreground text-sm">An owner or admin can connect Slack.</p>
          ) : (
            <p className="text-muted-foreground text-sm">
              This server has no integration encryption key, so it can&apos;t store a Slack webhook.
            </p>
          )}
        </Section>
      </div>
    </div>
  );
}
