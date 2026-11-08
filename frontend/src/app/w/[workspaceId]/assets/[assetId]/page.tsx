import Link from "next/link";

import { ActionForm, SubmitButton } from "@/components/action-form";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { EmptyState, formatDateTime, PageHeader, Section } from "@/components/page";
import { Badge, CriticalityBadge } from "@/components/ui/badge";
import { attempt } from "@/lib/attempt";
import { api, canManage } from "@/lib/relay-api";

import { setAssetStatusAction } from "../actions";
import { ASSET_TYPE_LABEL } from "../labels";

export default async function AssetPage({
  params,
}: PageProps<"/w/[workspaceId]/assets/[assetId]">) {
  const { workspaceId, assetId } = await params;
  const [workspace, asset] = await Promise.all([
    attempt(api.getWorkspace(workspaceId)),
    attempt(api.getAsset(workspaceId, assetId)),
  ]);
  if (!workspace.ok) return <ApiErrorNotice error={workspace.error} />;
  if (!asset.ok) return <ApiErrorNotice error={asset.error} />;
  const a = asset.data;
  const manage = canManage(workspace.data);
  const unowned = a.responsibilities.filter((r) => !r.primary_owner);

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader
        title={
          <span className="flex items-center gap-2">
            <Link href={`/w/${workspaceId}/assets`} className="text-muted-foreground font-normal">
              Assets
            </Link>
            <span className="text-muted-foreground">/</span>
            {a.name}
          </span>
        }
        actions={
          manage ? (
            <ActionForm
              action={setAssetStatusAction.bind(
                null,
                workspaceId,
                a.id,
                a.status === "active" ? "archived" : "active",
              )}
            >
              <SubmitButton size="sm" variant="ghost" pendingLabel="…">
                {a.status === "active" ? "Archive" : "Restore"}
              </SubmitButton>
            </ActionForm>
          ) : null
        }
      />
      <div className="flex max-w-4xl flex-col gap-8 p-6">
        <dl className="grid grid-cols-2 gap-x-8 gap-y-3 text-sm sm:grid-cols-4">
          <div>
            <dt className="text-muted-foreground text-xs">Type</dt>
            <dd>{ASSET_TYPE_LABEL[a.asset_type]}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground text-xs">Status</dt>
            <dd>{a.status === "active" ? "Active" : <Badge tone="muted">Archived</Badge>}</dd>
          </div>
          <div className="col-span-2">
            <dt className="text-muted-foreground text-xs">Link</dt>
            <dd className="truncate">
              {a.url ? (
                <a href={a.url} target="_blank" rel="noreferrer" className="hover:underline">
                  {a.url}
                </a>
              ) : (
                "—"
              )}
            </dd>
          </div>
          {a.description ? (
            <div className="col-span-full">
              <dt className="text-muted-foreground text-xs">Description</dt>
              <dd className="max-w-prose">{a.description}</dd>
            </div>
          ) : null}
        </dl>

        <Section
          title="Looked after by"
          description={`Added ${formatDateTime(a.created_at)}. Link responsibilities from their own page.`}
        >
          {unowned.length > 0 ? (
            <p className="text-sm text-amber-800 dark:text-amber-300">
              {unowned.length === 1
                ? "One linked responsibility has no primary owner."
                : `${unowned.length} linked responsibilities have no primary owner.`}
            </p>
          ) : null}
          {a.responsibilities.length === 0 ? (
            <EmptyState
              title="Not linked to any responsibility"
              description="Nobody is accountable for this asset until a responsibility stewards it."
            />
          ) : (
            <ul className="divide-y rounded-lg border">
              {a.responsibilities.map((r) => (
                <li key={r.id} className="flex flex-wrap items-center gap-3 px-4 py-2.5 text-sm">
                  <Link
                    href={`/w/${workspaceId}/responsibilities/${r.id}`}
                    className="min-w-0 flex-1 truncate font-medium hover:underline"
                  >
                    {r.name}
                  </Link>
                  <span className="text-muted-foreground text-xs">
                    {r.relationship === "stewards" ? "Stewards" : "Uses"}
                  </span>
                  <CriticalityBadge value={r.criticality} />
                  {r.primary_owner ? (
                    <span className="w-40 truncate text-right">{r.primary_owner.name}</span>
                  ) : (
                    <span className="w-40 text-right">
                      <Badge tone="warning">Unowned</Badge>
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Section>
      </div>
    </div>
  );
}
