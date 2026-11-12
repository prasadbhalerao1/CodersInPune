import type { Metadata } from "next";
import { ActionForm, Field, inputClass, SubmitButton } from "@/components/action-form";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { formatDateTime, PageHeader, Section } from "@/components/page";
import { attempt } from "@/lib/attempt";
import { api, canManage } from "@/lib/relay-api";
import { cn } from "@/lib/utils";

import { updatePolicyAction } from "../automations/actions";
import { SettingsNav } from "./settings-nav";

export const metadata: Metadata = { title: "Settings" };

export default async function PoliciesPage({ params }: PageProps<"/w/[workspaceId]/settings">) {
  const { workspaceId } = await params;
  const [workspace, policy] = await Promise.all([
    attempt(api.getWorkspace(workspaceId)),
    attempt(api.policy(workspaceId)),
  ]);
  if (!workspace.ok) return <ApiErrorNotice error={workspace.error} />;
  if (!policy.ok) return <ApiErrorNotice error={policy.error} />;
  const admin = canManage(workspace.data);
  const p = policy.data;

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader title="Settings" />
      <SettingsNav workspaceId={workspaceId} current="general" admin={admin} />
      <div className="flex max-w-3xl flex-col gap-8 p-6">
        <Section
          title="Continuity policies"
          description="These rules shape risks, knowledge freshness, insights and automations. Every change is audited."
        >
          <ActionForm
            action={updatePolicyAction.bind(null, workspaceId)}
            className="rounded-lg border p-4"
          >
            <fieldset disabled={!admin} className="flex flex-col gap-4">
              <label className="flex items-start gap-3 text-sm">
                <input
                  type="checkbox"
                  name="critical_requires_backup"
                  defaultChecked={p.critical_requires_backup}
                  className="mt-0.5 size-4"
                />
                <span>
                  <span className="font-medium">Critical responsibilities require a backup</span>
                  <span className="text-muted-foreground block text-xs">
                    A critical responsibility without a backup, or covered by a single person, is a
                    high risk. Off: it is a medium risk like other missing backups.
                  </span>
                </span>
              </label>
              <Field label="Knowledge review interval (days)" htmlFor="review-days">
                <input
                  id="review-days"
                  name="knowledge_review_days"
                  type="number"
                  min={7}
                  max={730}
                  required
                  defaultValue={p.knowledge_review_days}
                  className={cn(inputClass, "w-32")}
                />
              </Field>
              {admin ? (
                <div className="flex items-center gap-3">
                  <SubmitButton size="sm">Save policies</SubmitButton>
                  <span className="text-muted-foreground text-xs">
                    {p.updated_at
                      ? `Last changed by ${p.updated_by_name} · ${formatDateTime(p.updated_at)}`
                      : "Using the defaults"}
                  </span>
                </div>
              ) : (
                <p className="text-muted-foreground text-xs">
                  Only owners and admins can change policies.
                </p>
              )}
            </fieldset>
          </ActionForm>
        </Section>
      </div>
    </div>
  );
}
