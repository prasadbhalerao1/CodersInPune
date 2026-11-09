import type { Metadata } from "next";
import { ActionForm, SubmitButton } from "@/components/action-form";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { formatDateTime, PageHeader, Section } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { attempt } from "@/lib/attempt";
import { api, canManage } from "@/lib/relay-api";

import { SettingsNav } from "../settings-nav";
import { TestEmailButton } from "./test-email";
import { retryEmailAction, savePreferencesAction } from "./actions";

export const metadata: Metadata = { title: "Notifications" };

const ERROR_HELP: Record<string, string> = {
  timeout: "The provider didn't answer in time. Retrying usually works.",
  email_not_configured: "Email was not configured when this was sent.",
};

function explain(code: string | null): string {
  if (!code) return "";
  if (ERROR_HELP[code]) return ERROR_HELP[code];
  if (code.startsWith("provider_")) return "The provider was unavailable. Retrying usually works.";
  if (code.startsWith("rejected_4")) {
    return "The provider rejected the message. Check the sender domain and recipient, then retry.";
  }
  return code;
}

export default async function NotificationSettingsPage({
  params,
}: PageProps<"/w/[workspaceId]/settings/notifications">) {
  const { workspaceId } = await params;
  const [workspace, preferences] = await Promise.all([
    attempt(api.getWorkspace(workspaceId)),
    attempt(api.notificationPreferences(workspaceId)),
  ]);
  if (!workspace.ok) return <ApiErrorNotice error={workspace.error} />;
  if (!preferences.ok) return <ApiErrorNotice error={preferences.error} />;
  const admin = canManage(workspace.data);
  const status = admin ? await attempt(api.emailStatus(workspaceId)) : null;

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader title="Settings" />
      <SettingsNav workspaceId={workspaceId} current="notifications" admin={admin} />
      <div className="flex max-w-3xl flex-col gap-8 p-6">
        <Section
          title="Email me about"
          description="In-app notifications are always on; these choose what also arrives by email."
        >
          <ActionForm
            action={savePreferencesAction.bind(null, workspaceId)}
            className="rounded-lg border"
          >
            <ul className="divide-y">
              {preferences.data.map((p) => (
                <li key={p.category}>
                  <label className="flex cursor-pointer items-center justify-between gap-4 px-4 py-3 text-sm">
                    <span>{p.label}</span>
                    <input
                      type="checkbox"
                      name="enabled"
                      value={p.category}
                      defaultChecked={p.enabled}
                      className="size-4"
                    />
                  </label>
                </li>
              ))}
            </ul>
            <div className="border-t px-4 py-3">
              <SubmitButton size="sm">Save preferences</SubmitButton>
            </div>
          </ActionForm>
        </Section>

        {status ? (
          !status.ok ? (
            <ApiErrorNotice error={status.error} />
          ) : (
            <Section
              title="Email delivery"
              description="Workspace-wide delivery health. Only owners and admins see this."
            >
              <div className="rounded-lg border p-4 text-sm">
                <p className="flex flex-wrap items-center gap-2">
                  {!status.data.configured ? (
                    <Badge tone="muted">Not configured</Badge>
                  ) : status.data.healthy ? (
                    <Badge tone="neutral">Healthy</Badge>
                  ) : (
                    <Badge tone="warning">Failures in the last 24 hours</Badge>
                  )}
                  {status.data.sender ? (
                    <span className="text-muted-foreground">Sending as {status.data.sender}</span>
                  ) : null}
                </p>
                {status.data.configured ? (
                  <>
                    <p className="text-muted-foreground mt-2 text-xs tabular-nums">
                      {status.data.provider ? `Via ${status.data.provider} · ` : ""}
                      {status.data.sent_24h} sent · {status.data.failed_24h} failed in the last 24
                      hours · {status.data.pending} waiting
                    </p>
                    <TestEmailButton workspaceId={workspaceId} />
                  </>
                ) : (
                  <p className="text-muted-foreground mt-2 text-xs">
                    Set RELAY_SMTP_HOST (or RELAY_RESEND_API_KEY) and RELAY_EMAIL_FROM on the server
                    to turn on email. Until then, notifications are in-app only and invitations use
                    WorkOS.
                  </p>
                )}
              </div>
              {status.data.recent_failures.length ? (
                <ul className="divide-y rounded-lg border">
                  {status.data.recent_failures.map((f) => (
                    <li
                      key={f.id}
                      className="flex flex-wrap items-center gap-3 px-4 py-2.5 text-sm"
                    >
                      <span className="min-w-0 flex-1">
                        <span className="font-medium">{f.kind.replaceAll("_", " ")}</span>
                        <span className="text-muted-foreground"> to {f.recipient}</span>
                        <span className="text-muted-foreground block text-xs">
                          {explain(f.last_error)} · {f.attempts} attempts ·{" "}
                          {formatDateTime(f.created_at)}
                        </span>
                      </span>
                      <ActionForm action={retryEmailAction.bind(null, workspaceId, f.id)}>
                        <SubmitButton size="sm" variant="outline" pendingLabel="…">
                          Retry
                        </SubmitButton>
                      </ActionForm>
                    </li>
                  ))}
                </ul>
              ) : null}
            </Section>
          )
        ) : null}
      </div>
    </div>
  );
}
