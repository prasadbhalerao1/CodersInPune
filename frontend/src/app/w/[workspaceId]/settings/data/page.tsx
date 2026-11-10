import type { Metadata } from "next";

import { ActionForm, Field, inputClass, SubmitButton } from "@/components/action-form";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { formatDateTime, PageHeader, Section } from "@/components/page";
import { attempt } from "@/lib/attempt";
import { api, canManage } from "@/lib/relay-api";
import { cn } from "@/lib/utils";

import { SettingsNav } from "../settings-nav";
import {
  applyRetentionAction,
  cancelDeletionAction,
  scheduleDeletionAction,
  setRetentionAction,
  transferOwnershipAction,
} from "./actions";

export const metadata: Metadata = { title: "Data & privacy" };

const READS = [
  {
    source: "Relay itself",
    what: "Responsibilities, owners and their history, cases, tasks, approvals, knowledge and comments people write here.",
    why: "This is the continuity record Relay keeps for you.",
  },
  {
    source: "GitHub (read-only)",
    what: "Repository metadata, CODEOWNERS, catalog-info.yaml, maintainers, pull request and issue titles and states.",
    why: "To suggest owners, show open work on a responsibility and flag unowned activity. Source code is never read.",
  },
  {
    source: "Linear (read-only by default)",
    what: "Teams, projects, users and issue titles, states, labels and assignees.",
    why: "To show open work and deadlines in handovers. Issue creation is off unless an admin enables it and approves each issue.",
  },
  {
    source: "Notion (pages you share)",
    what: "Only the pages and databases you explicitly share with the integration, with their revision.",
    why: "To import procedures as knowledge. Imported pages stay unverified until a person reviews them; unshared pages are withdrawn.",
  },
  {
    source: "AI (when switched on)",
    what: "The evidence a case is allowed to share, never private messages or files. Prompts are not stored.",
    why: "To draft findings and handovers that cite their sources. People approve everything; no AI can change data.",
  },
];

export default async function DataPage({ params }: PageProps<"/w/[workspaceId]/settings/data">) {
  const { workspaceId } = await params;
  const [workspace, policy, members] = await Promise.all([
    attempt(api.getWorkspace(workspaceId)),
    attempt(api.policy(workspaceId)),
    attempt(api.members(workspaceId)),
  ]);
  if (!workspace.ok) return <ApiErrorNotice error={workspace.error} />;
  if (!policy.ok) return <ApiErrorNotice error={policy.error} />;
  const admin = canManage(workspace.data);
  const owner = workspace.data.role === "owner";
  const others = members.ok
    ? members.data.filter((m) => m.status === "active" && m.role !== "owner")
    : [];

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader title="Settings" />
      <SettingsNav workspaceId={workspaceId} current="data" admin={admin} />
      <div className="flex max-w-4xl flex-col gap-8 p-6">
        <Section
          title="What Relay reads, and why"
          description="Everything Relay can see comes from one of these, scoped to this workspace."
        >
          <ul className="divide-y rounded-lg border text-sm">
            {READS.map((r) => (
              <li key={r.source} className="grid gap-1 px-4 py-3 sm:grid-cols-[12rem_1fr]">
                <span className="font-medium">{r.source}</span>
                <span>
                  {r.what}
                  <span className="text-muted-foreground block text-xs">{r.why}</span>
                </span>
              </li>
            ))}
          </ul>
        </Section>

        {admin ? (
          <Section
            title="Export"
            description="Everything in this workspace as JSON, or the audit log as CSV. Each export is itself audited."
          >
            <div className="flex flex-wrap gap-2 text-sm">
              <a
                href={`/w/${workspaceId}/settings/data/download?kind=workspace`}
                className="hover:bg-muted rounded-md border px-3 py-1.5 font-medium"
              >
                Download workspace data (JSON)
              </a>
              <a
                href={`/w/${workspaceId}/settings/data/download?kind=audit`}
                className="hover:bg-muted rounded-md border px-3 py-1.5 font-medium"
              >
                Download audit log (CSV)
              </a>
            </div>
          </Section>
        ) : null}

        <Section
          title="Retention"
          description="Read notifications, integration sync history and AI step logs older than this are deleted. Audit events, cases, ownership history and knowledge versions are kept."
        >
          {admin ? (
            <div className="flex flex-wrap items-end gap-3">
              <ActionForm
                action={setRetentionAction.bind(null, workspaceId)}
                className="flex-row items-end gap-2"
              >
                <Field label="Keep for (days)" htmlFor="retention">
                  <input
                    id="retention"
                    name="retention_days"
                    type="number"
                    min={30}
                    max={3650}
                    defaultValue={policy.data.retention_days}
                    className={cn(inputClass, "w-32")}
                  />
                </Field>
                <SubmitButton size="sm" variant="outline" pendingLabel="Saving…">
                  Save
                </SubmitButton>
              </ActionForm>
              <ActionForm action={applyRetentionAction.bind(null, workspaceId)}>
                <SubmitButton
                  size="sm"
                  variant="ghost"
                  pendingLabel="Applying…"
                  confirm="Delete operational records older than the retention period now?"
                >
                  Apply now
                </SubmitButton>
              </ActionForm>
            </div>
          ) : (
            <p className="text-sm">{policy.data.retention_days} days.</p>
          )}
          <p className="text-muted-foreground text-xs">
            It also runs automatically with scheduled automations.
          </p>
        </Section>

        {owner ? (
          <Section
            title="Transfer ownership"
            description="Hand the workspace to another member. You become an admin."
          >
            <ActionForm
              action={transferOwnershipAction.bind(null, workspaceId)}
              className="flex-row items-end gap-2"
            >
              <select
                name="user_id"
                required
                defaultValue=""
                aria-label="New owner"
                className={cn(inputClass, "w-64")}
              >
                <option value="" disabled>
                  Choose a member…
                </option>
                {others.map((m) => (
                  <option key={m.user_id} value={m.user_id}>
                    {m.name}
                  </option>
                ))}
              </select>
              <SubmitButton
                size="sm"
                variant="outline"
                pendingLabel="Transferring…"
                confirm="Transfer ownership? You'll become an admin."
              >
                Transfer
              </SubmitButton>
            </ActionForm>
          </Section>
        ) : null}

        {owner ? (
          <section id="delete" className="border-destructive/40 scroll-mt-6 rounded-lg border p-4">
            <h2 className="font-semibold">Delete workspace</h2>
            {workspace.data.deletion_scheduled_for ? (
              <div className="mt-2 flex flex-wrap items-center gap-3 text-sm">
                <p className="flex-1">
                  Scheduled for permanent deletion on{" "}
                  <strong>{formatDateTime(workspace.data.deletion_scheduled_for)}</strong>. Until
                  then everything keeps working and you can cancel.
                </p>
                <ActionForm action={cancelDeletionAction.bind(null, workspaceId)}>
                  <SubmitButton size="sm" variant="outline" pendingLabel="Cancelling…">
                    Cancel deletion
                  </SubmitButton>
                </ActionForm>
              </div>
            ) : (
              <>
                <p className="text-muted-foreground mt-1 text-sm">
                  Everything in this workspace, including its audit log, is permanently deleted
                  30 days after you confirm. Export first if you need a copy. You can cancel at
                  any time during those 30 days.
                </p>
                <ActionForm
                  action={scheduleDeletionAction.bind(null, workspaceId)}
                  className="mt-3 flex-row flex-wrap items-end gap-2"
                >
                  <Field label={`Type “${workspace.data.name}” to confirm`} htmlFor="confirm-name">
                    <input
                      id="confirm-name"
                      name="confirm_name"
                      required
                      autoComplete="off"
                      className={cn(inputClass, "w-64")}
                    />
                  </Field>
                  <SubmitButton
                    size="sm"
                    variant="destructive"
                    pendingLabel="Scheduling…"
                    confirm="Schedule this workspace for permanent deletion in 30 days?"
                  >
                    Delete workspace
                  </SubmitButton>
                </ActionForm>
              </>
            )}
          </section>
        ) : null}
      </div>
    </div>
  );
}
