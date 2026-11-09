import type { Metadata } from "next";
import Link from "next/link";

import { ActionForm, Field, inputClass, SubmitButton } from "@/components/action-form";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { EmptyState, PageHeader, Section } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { attempt } from "@/lib/attempt";
import { api, canManage } from "@/lib/relay-api";

import { createAssetAction } from "./actions";
import { ASSET_TYPE_LABEL, ASSET_TYPES } from "./labels";

export const metadata: Metadata = { title: "Assets" };

export default async function AssetsPage({
  params,
  searchParams,
}: PageProps<"/w/[workspaceId]/assets">) {
  const [{ workspaceId }, query] = await Promise.all([params, searchParams]);
  const pick = (key: string) => (typeof query[key] === "string" ? query[key] : undefined);
  const filters = {
    q: pick("q"),
    asset_type: pick("asset_type"),
    status: pick("status") ?? "active",
  };
  const [workspace, assets] = await Promise.all([
    attempt(api.getWorkspace(workspaceId)),
    attempt(api.assets(workspaceId, filters)),
  ]);
  if (!workspace.ok) return <ApiErrorNotice error={workspace.error} />;
  if (!assets.ok) return <ApiErrorNotice error={assets.error} />;
  const manage = canManage(workspace.data);
  const base = `/w/${workspaceId}/assets`;
  const filtered = Boolean(filters.q || filters.asset_type || filters.status !== "active");

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader title="Assets" />
      <div className="flex max-w-5xl flex-col gap-6 p-6">
        <p className="text-muted-foreground max-w-prose text-sm">
          Repositories, services, vendors and processes your responsibilities look after. Assets
          have no owners of their own: ownership always comes from the linked responsibilities.
        </p>
        {manage ? (
          <Section title="Add an asset">
            <ActionForm
              action={createAssetAction.bind(null, workspaceId)}
              className="rounded-lg border p-4"
            >
              <div className="grid gap-3 sm:grid-cols-4">
                <Field label="Name" htmlFor="asset-name">
                  <input
                    id="asset-name"
                    name="name"
                    required
                    maxLength={200}
                    className={inputClass}
                  />
                </Field>
                <Field label="Type" htmlFor="asset-type">
                  <select id="asset-type" name="asset_type" className={inputClass}>
                    {ASSET_TYPES.map((t) => (
                      <option key={t} value={t}>
                        {ASSET_TYPE_LABEL[t]}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Link (optional)" htmlFor="asset-url">
                  <input
                    id="asset-url"
                    name="url"
                    type="url"
                    pattern="https?://.+"
                    placeholder="https://"
                    className={inputClass}
                  />
                </Field>
                <Field label="Description (optional)" htmlFor="asset-description">
                  <input
                    id="asset-description"
                    name="description"
                    maxLength={4000}
                    className={inputClass}
                  />
                </Field>
              </div>
              <div>
                <SubmitButton size="sm">Add asset</SubmitButton>
              </div>
            </ActionForm>
          </Section>
        ) : null}

        <form className="flex flex-wrap gap-2" role="search">
          <input
            name="q"
            defaultValue={filters.q}
            placeholder="Search assets"
            aria-label="Search"
            className={`${inputClass} max-w-xs`}
          />
          <select
            name="asset_type"
            defaultValue={filters.asset_type ?? ""}
            aria-label="Type"
            className={`${inputClass} w-44`}
          >
            <option value="">Any type</option>
            {ASSET_TYPES.map((t) => (
              <option key={t} value={t}>
                {ASSET_TYPE_LABEL[t]}
              </option>
            ))}
          </select>
          <select
            name="status"
            defaultValue={filters.status}
            aria-label="Status"
            className={`${inputClass} w-32`}
          >
            <option value="active">Active</option>
            <option value="archived">Archived</option>
          </select>
          <button type="submit" className={buttonVariants({ variant: "outline" })}>
            Apply
          </button>
          {filtered ? (
            <Link href={base} className={buttonVariants({ variant: "ghost" })}>
              Clear
            </Link>
          ) : null}
        </form>

        {assets.data.length === 0 ? (
          <EmptyState
            title={filtered ? "No matching assets" : "No assets yet"}
            description={
              filtered
                ? "Try a different search or clear the filters."
                : "Record the systems and vendors your responsibilities depend on."
            }
          />
        ) : (
          <div className="overflow-x-auto rounded-lg border">
            <table className="w-full text-sm">
              <thead className="text-muted-foreground bg-muted/40 text-left text-xs">
                <tr>
                  <th className="px-4 py-2 font-medium">Name</th>
                  <th className="px-4 py-2 font-medium">Type</th>
                  <th className="px-4 py-2 font-medium">Responsibilities</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {assets.data.map((a) => (
                  <tr key={a.id} className="hover:bg-muted/40">
                    <td className="px-4 py-2.5">
                      <Link href={`${base}/${a.id}`} className="font-medium hover:underline">
                        {a.name}
                      </Link>
                      {a.description ? (
                        <span className="text-muted-foreground block truncate text-xs">
                          {a.description}
                        </span>
                      ) : null}
                    </td>
                    <td className="px-4 py-2.5">
                      <Badge tone="muted">{ASSET_TYPE_LABEL[a.asset_type]}</Badge>
                    </td>
                    <td className="px-4 py-2.5 tabular-nums">
                      {a.responsibility_count > 0 ? (
                        a.responsibility_count
                      ) : (
                        <Badge tone="warning">Not linked</Badge>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
