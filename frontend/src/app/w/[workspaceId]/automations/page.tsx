import Link from "next/link";

import { ActionForm, inputClass, SubmitButton } from "@/components/action-form";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { formatDateTime, PageHeader } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { attempt } from "@/lib/attempt";
import { api } from "@/lib/relay-api";
import type { AutomationRuleView, WorkspaceMemberView } from "@/lib/types";
import { cn } from "@/lib/utils";

import { SettingsNav } from "../settings/settings-nav";
import { runAutomationAction, updateAutomationAction } from "./actions";

const STATUS = {
  never: { label: "Not run yet", tone: "muted" },
  ok: { label: "Last run OK", tone: "neutral" },
  failed: { label: "Last run failed", tone: "danger" },
} as const;

export default async function AutomationsPage({
  params,
}: PageProps<"/w/[workspaceId]/automations">) {
  const { workspaceId } = await params;
  const [rules, members] = await Promise.all([
    attempt(api.automations(workspaceId)),
    attempt(api.members(workspaceId)),
  ]);
  if (!rules.ok) return <ApiErrorNotice error={rules.error} />;
  const active = members.ok ? members.data.filter((m) => m.status === "active") : [];

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader title="Settings" />
      <SettingsNav workspaceId={workspaceId} current="automations" admin />
      <div className="flex max-w-5xl flex-col gap-4 p-6">
        <p className="text-muted-foreground max-w-2xl text-sm">
          Automations watch for continuity gaps once a day and nudge people. They never change
          owners, approvals or cases. Alerts without an assignee go to workspace owners and admins;
          follow-ups appear in the assignee&apos;s{" "}
          <Link href={`/w/${workspaceId}/my-work`} className="underline">
            My Work
          </Link>
          .
        </p>
        <ul className="divide-y rounded-lg border">
          {rules.data.map((rule) => (
            <Rule key={rule.template} workspaceId={workspaceId} rule={rule} members={active} />
          ))}
        </ul>
      </div>
    </div>
  );
}

function Rule({
  workspaceId,
  rule,
  members,
}: {
  workspaceId: string;
  rule: AutomationRuleView;
  members: WorkspaceMemberView[];
}) {
  const status = STATUS[rule.last_status];
  return (
    <li className="flex flex-col gap-3 px-4 py-4">
      <div className="flex flex-wrap items-start gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium">{rule.title}</p>
          <p className="text-muted-foreground text-xs">{rule.description}</p>
        </div>
        {rule.enabled ? <Badge tone="neutral">On</Badge> : <Badge tone="muted">Off</Badge>}
        <Badge tone={status.tone}>{status.label}</Badge>
      </div>
      <ActionForm
        action={updateAutomationAction.bind(null, workspaceId, rule.template)}
        className="flex-row flex-wrap items-center gap-3"
      >
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" name="enabled" defaultChecked={rule.enabled} className="size-4" />
          Enabled
        </label>
        <select
          name="action"
          defaultValue={rule.action}
          aria-label={`Action for ${rule.title}`}
          className={cn(inputClass, "h-8 w-44")}
        >
          <option value="notify">Notify</option>
          <option value="create_follow_up">Create a follow-up</option>
        </select>
        <select
          name="assignee_user_id"
          defaultValue={rule.assignee_user_id ?? ""}
          aria-label={`Assignee for ${rule.title}`}
          className={cn(inputClass, "h-8 w-52")}
        >
          <option value="">Owners and admins (default)</option>
          {members.map((m) => (
            <option key={m.user_id} value={m.user_id}>
              {m.name}
            </option>
          ))}
        </select>
        <SubmitButton size="sm" variant="outline">
          Save
        </SubmitButton>
      </ActionForm>
      <div className="text-muted-foreground flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
        <span>
          {rule.last_run_at ? `Last run ${formatDateTime(rule.last_run_at)}` : "Never run"}
          {rule.next_run_at ? ` · next ${formatDateTime(rule.next_run_at)}` : ""}
        </span>
        {rule.open_follow_ups ? <span>{rule.open_follow_ups} open follow-ups</span> : null}
        <span className="flex-1" />
        <ActionForm action={runAutomationAction.bind(null, workspaceId, rule.template, false)}>
          <SubmitButton size="sm" variant="ghost" pendingLabel="Queuing…">
            Run now
          </SubmitButton>
        </ActionForm>
        {rule.last_status === "failed" ? (
          <ActionForm action={runAutomationAction.bind(null, workspaceId, rule.template, true)}>
            <SubmitButton size="sm" variant="outline" pendingLabel="Queuing…">
              Retry
            </SubmitButton>
          </ActionForm>
        ) : null}
      </div>
      {rule.last_error ? (
        <p
          role="status"
          className="rounded-md border border-amber-600/20 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:bg-amber-950/30 dark:text-amber-200"
        >
          {rule.last_error}. Nothing from the failed run was kept; retrying is safe.
        </p>
      ) : null}
      {rule.runs.length ? (
        <details className="text-xs">
          <summary className="text-muted-foreground hover:text-foreground cursor-pointer select-none">
            Execution history ({rule.runs.length})
          </summary>
          <div className="mt-2 overflow-x-auto">
            <table className="w-full text-left">
              <thead className="text-muted-foreground">
                <tr>
                  <th className="py-1 font-normal">Started</th>
                  <th className="py-1 font-normal">Trigger</th>
                  <th className="py-1 font-normal">Result</th>
                  <th className="py-1 text-right font-normal">Matched</th>
                  <th className="py-1 text-right font-normal">Actions</th>
                </tr>
              </thead>
              <tbody>
                {rule.runs.map((run) => (
                  <tr key={run.id} className="border-t">
                    <td className="py-1">{formatDateTime(run.started_at)}</td>
                    <td className="py-1 capitalize">{run.trigger}</td>
                    <td className={cn("py-1", run.status === "failed" && "text-red-700")}>
                      {run.status === "ok" ? "OK" : "Failed"}
                    </td>
                    <td className="py-1 text-right tabular-nums">{run.matched}</td>
                    <td className="py-1 text-right tabular-nums">{run.actions}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      ) : null}
    </li>
  );
}
