import type { Metadata } from "next";

import { ActionForm, Field, inputClass, SubmitButton } from "@/components/action-form";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { PageHeader, Section } from "@/components/page";
import { Badge, CriticalityBadge } from "@/components/ui/badge";
import { attempt } from "@/lib/attempt";
import { api, canManage } from "@/lib/relay-api";

import { createResponsibilityTypeAction, updateTierAction } from "../../actions";
import { SettingsNav } from "../settings-nav";

export const metadata: Metadata = { title: "Types & tiers" };

export default async function GovernanceSettingsPage({
  params,
}: PageProps<"/w/[workspaceId]/settings/governance">) {
  const { workspaceId } = await params;
  const [workspace, types, tiers] = await Promise.all([
    attempt(api.getWorkspace(workspaceId)),
    attempt(api.responsibilityTypes(workspaceId)),
    attempt(api.policyTiers(workspaceId)),
  ]);
  if (!workspace.ok) return <ApiErrorNotice error={workspace.error} />;
  if (!types.ok) return <ApiErrorNotice error={types.error} />;
  if (!tiers.ok) return <ApiErrorNotice error={tiers.error} />;
  const admin = canManage(workspace.data);

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader title="Settings" />
      <SettingsNav workspaceId={workspaceId} current="governance" admin={admin} />
      <div className="flex max-w-4xl flex-col gap-8 p-6">
        <Section
          title="Criticality tiers"
          description="What each criticality requires. Risks and review reminders follow these."
        >
          <ul className="divide-y rounded-lg border">
            {tiers.data.map((t) => (
              <li key={t.criticality} className="px-4 py-3 text-sm">
                <ActionForm
                  action={updateTierAction.bind(null, workspaceId, t.criticality)}
                  className="flex-row flex-wrap items-center gap-4"
                >
                  <span className="w-24">
                    <CriticalityBadge value={t.criticality} />
                  </span>
                  <label className="flex items-center gap-1.5">
                    <input
                      type="checkbox"
                      name="requires_backup"
                      defaultChecked={t.requires_backup}
                      disabled={!admin}
                    />
                    Backup required
                  </label>
                  <label className="flex items-center gap-1.5">
                    <input
                      type="checkbox"
                      name="requires_accountable_contact"
                      defaultChecked={t.requires_accountable_contact}
                      disabled={!admin}
                    />
                    Team owners need a named contact
                  </label>
                  <label className="flex items-center gap-1.5">
                    Review every
                    <input
                      type="number"
                      name="review_days"
                      min={7}
                      max={730}
                      defaultValue={t.review_days}
                      disabled={!admin}
                      aria-label={`Review days for ${t.criticality}`}
                      className={`${inputClass} h-8 w-20`}
                    />
                    days
                  </label>
                  {t.customised ? <Badge tone="muted">Custom</Badge> : null}
                  {admin ? (
                    <SubmitButton size="sm" variant="outline" pendingLabel="…">
                      Save
                    </SubmitButton>
                  ) : null}
                </ActionForm>
              </li>
            ))}
          </ul>
        </Section>

        <Section
          title="Responsibility types"
          description="Managed types replace free-text categories, so filters and reports stay consistent."
        >
          {types.data.length ? (
            <ul className="divide-y rounded-lg border text-sm">
              {types.data.map((t) => (
                <li key={t.id} className="flex items-center gap-3 px-4 py-2.5">
                  <span className="flex-1 font-medium">{t.name}</span>
                  {t.review_cadence_days ? (
                    <span className="text-muted-foreground text-xs">
                      review every {t.review_cadence_days} days
                    </span>
                  ) : null}
                  <span className="text-muted-foreground text-xs tabular-nums">
                    {t.responsibilities} in use
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-muted-foreground text-sm">No types yet.</p>
          )}
          {admin ? (
            <ActionForm
              action={createResponsibilityTypeAction.bind(null, workspaceId)}
              className="flex-row flex-wrap items-end gap-2"
            >
              <Field label="Name" htmlFor="type-name">
                <input id="type-name" name="name" required maxLength={80} className={inputClass} />
              </Field>
              <Field label="Review every (days, optional)" htmlFor="type-days">
                <input
                  id="type-days"
                  name="review_cadence_days"
                  type="number"
                  min={7}
                  max={730}
                  className={inputClass}
                />
              </Field>
              <SubmitButton size="sm" variant="outline" pendingLabel="Adding…">
                Add type
              </SubmitButton>
            </ActionForm>
          ) : null}
        </Section>
      </div>
    </div>
  );
}
