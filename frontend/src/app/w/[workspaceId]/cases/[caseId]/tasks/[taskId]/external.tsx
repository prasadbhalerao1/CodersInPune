import { ActionForm, Field, inputClass, SubmitButton } from "@/components/action-form";
import { formatDateTime, Section } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import type { ExternalActionView, ExternalTargetsView, TaskView } from "@/lib/types";
import { cn } from "@/lib/utils";

import { approveExternalAction, checkExternalAction, retryExternalAction } from "../../../actions";

const STATE = {
  approved: { label: "Approved · queued", tone: "muted" },
  executing: { label: "Creating…", tone: "muted" },
  succeeded: { label: "Created", tone: "neutral" },
  uncertain: { label: "Checking whether it was created", tone: "warning" },
  failed: { label: "Failed", tone: "danger" },
} as const;

/** Mirror a task as a GitHub or Linear issue: review the exact content, approve, track. */
export function ExternalPanel({
  workspaceId,
  caseId,
  task,
  targets,
  actions,
}: {
  workspaceId: string;
  caseId: string;
  task: TaskView;
  targets: ExternalTargetsView;
  actions: ExternalActionView[];
}) {
  const live = actions.find((a) => a.state !== "failed");
  const usable = targets.targets.filter((t) =>
    t.provider === "github" ? targets.github_enabled : targets.linear_enabled,
  );
  return (
    <Section
      title="External issue"
      description="Optionally mirror this task in GitHub or Linear. Nothing is created until you approve the exact content below."
    >
      {actions.length ? (
        <ul className="divide-y rounded-lg border text-sm">
          {actions.map((a) => (
            <li key={a.id} className="flex flex-col gap-1.5 px-4 py-3">
              <p className="flex flex-wrap items-center gap-2">
                <Badge tone={STATE[a.state].tone}>{STATE[a.state].label}</Badge>
                <span className="font-medium">{a.target_label}</span>
                {a.external_url ? (
                  <a href={a.external_url} target="_blank" rel="noreferrer" className="underline">
                    Open issue ↗
                  </a>
                ) : null}
              </p>
              <p className="text-muted-foreground text-xs">
                Approved by {a.approved_by_name ?? "—"} · {formatDateTime(a.approved_at)} ·{" "}
                {a.attempts} attempt{a.attempts === 1 ? "" : "s"}
                {a.receipt.recovered_existing ? " · recovered after a timeout, no duplicate" : ""}
              </p>
              {a.error ? <p className="text-xs text-red-700 dark:text-red-300">{a.error}</p> : null}
              <div className="flex gap-2">
                {a.state === "failed" || a.state === "uncertain" ? (
                  <ActionForm action={retryExternalAction.bind(null, workspaceId, a.id)}>
                    <SubmitButton size="sm" variant="outline" pendingLabel="…">
                      Retry safely
                    </SubmitButton>
                  </ActionForm>
                ) : null}
                {a.state === "succeeded" ? (
                  <ActionForm action={checkExternalAction.bind(null, workspaceId, a.id)}>
                    <SubmitButton size="sm" variant="ghost" pendingLabel="Checking…">
                      Check status
                    </SubmitButton>
                  </ActionForm>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      ) : null}
      {!live && task.status === "open" ? (
        usable.length ? (
          <ActionForm
            action={approveExternalAction.bind(null, workspaceId, caseId, task.id)}
            className="rounded-lg border p-4"
          >
            <Field label="Destination" htmlFor="ext-target">
              <select id="ext-target" name="target" required defaultValue="" className={inputClass}>
                <option value="" disabled>
                  Choose a repository or team…
                </option>
                {usable.map((t) => (
                  <option key={`${t.provider}:${t.target}`} value={`${t.provider}:${t.target}`}>
                    {t.provider === "github" ? "GitHub" : "Linear"} · {t.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Issue title (sent exactly as written)" htmlFor="ext-title">
              <input
                id="ext-title"
                name="title"
                required
                maxLength={200}
                defaultValue={task.title}
                className={inputClass}
              />
            </Field>
            <Field label="Issue body" htmlFor="ext-body">
              <textarea
                id="ext-body"
                name="body"
                rows={4}
                maxLength={4000}
                defaultValue={task.description ?? ""}
                className={cn(inputClass, "h-auto py-2")}
              />
            </Field>
            <p className="text-muted-foreground text-xs">
              Relay adds a reference line so a retry never creates a second issue. Your approval is
              recorded with the content.
            </p>
            <SubmitButton
              size="sm"
              pendingLabel="Approving…"
              confirm="Create this issue exactly as shown?"
            >
              Approve and create
            </SubmitButton>
          </ActionForm>
        ) : (
          <p className="text-muted-foreground text-sm">
            {targets.github_blocker && targets.linear_blocker
              ? "External issue creation is off. "
              : "No reachable repository or team. "}
            {targets.linear_blocker ?? targets.github_blocker}
          </p>
        )
      ) : null}
    </Section>
  );
}
