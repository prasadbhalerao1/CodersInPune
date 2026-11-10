import type { Metadata } from "next";
import Link from "next/link";

import { inputClass } from "@/components/action-form";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { PageNav } from "@/components/page-nav";
import { EmptyState, PageHeader } from "@/components/page";
import { SavedViews } from "@/components/saved-views";
import { Badge, CriticalityBadge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { attempt } from "@/lib/attempt";
import { api, canManage } from "@/lib/relay-api";

export const metadata: Metadata = { title: "Responsibilities" };

export default async function ResponsibilitiesPage({
  params,
  searchParams,
}: PageProps<"/w/[workspaceId]/responsibilities">) {
  const [{ workspaceId }, query] = await Promise.all([params, searchParams]);
  const pick = (key: string) => (typeof query[key] === "string" ? query[key] : undefined);
  const filters = {
    q: pick("q"),
    criticality: pick("criticality"),
    status: pick("status") ?? "active",
    department_id: pick("department_id"),
    type_id: pick("type_id"),
    has_backup: pick("has_backup"),
    review: pick("review"),
    needs_verification: pick("needs_verification"),
  };
  const after = pick("after");
  const currentQuery = new URLSearchParams(
    Object.entries(filters).filter((e): e is [string, string] => Boolean(e[1])),
  ).toString();
  const [workspace, list, departments, types, views] = await Promise.all([
    attempt(api.getWorkspace(workspaceId)),
    attempt(
      api.listResponsibilities(
        workspaceId,
        Object.fromEntries(Object.entries({ ...filters, after }).filter(([, v]) => v)) as Record<
          string,
          string
        >,
      ),
    ),
    attempt(api.departments(workspaceId)),
    attempt(api.responsibilityTypes(workspaceId)),
    attempt(api.savedViews(workspaceId, "responsibilities")),
  ]);
  if (!workspace.ok) return <ApiErrorNotice error={workspace.error} />;
  if (!list.ok) return <ApiErrorNotice error={list.error} />;
  const base = `/w/${workspaceId}/responsibilities`;
  const filtered = Boolean(
    filters.q ||
    filters.criticality ||
    filters.department_id ||
    filters.type_id ||
    filters.has_backup ||
    filters.review ||
    filters.needs_verification ||
    filters.status !== "active",
  );
  const select = `${inputClass} w-40`;
  const departmentOptions = departments.ok ? departments.data : [];
  const manage = canManage(workspace.data);

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader
        title="Responsibilities"
        actions={
          manage ? (
            <>
              <Link
                href={`/w/${workspaceId}/import`}
                className={buttonVariants({ size: "sm", variant: "ghost" })}
              >
                Import CSV
              </Link>
              <Link href={`${base}/new`} className={buttonVariants({ size: "sm" })}>
                New responsibility
              </Link>
            </>
          ) : null
        }
      />
      <div className="flex flex-col gap-4 p-6">
        <form className="flex flex-wrap gap-2" role="search">
          <input
            name="q"
            defaultValue={filters.q}
            placeholder="Search name, description or category"
            aria-label="Search"
            className={`${inputClass} max-w-sm`}
          />
          <select
            name="criticality"
            defaultValue={filters.criticality ?? ""}
            aria-label="Criticality"
            className={`${inputClass} w-40`}
          >
            <option value="">Any criticality</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="standard">Standard</option>
            <option value="low">Low</option>
          </select>
          {departmentOptions.length > 0 ? (
            <select
              name="department_id"
              defaultValue={filters.department_id ?? ""}
              aria-label="Department"
              className={`${inputClass} w-44`}
            >
              <option value="">Any department</option>
              {departmentOptions.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </select>
          ) : null}
          {types.ok && types.data.length ? (
            <select
              name="type_id"
              defaultValue={filters.type_id ?? ""}
              aria-label="Type"
              className={select}
            >
              <option value="">Any type</option>
              {types.data.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
          ) : null}
          <select
            name="has_backup"
            defaultValue={filters.has_backup ?? ""}
            aria-label="Backup"
            className={select}
          >
            <option value="">Backup: any</option>
            <option value="true">Has a backup</option>
            <option value="false">No backup</option>
          </select>
          <select
            name="review"
            defaultValue={filters.review ?? ""}
            aria-label="Review state"
            className={select}
          >
            <option value="">Review: any</option>
            <option value="due">Review overdue</option>
            <option value="ok">Reviewed</option>
          </select>
          <label className="flex items-center gap-1.5 text-sm">
            <input
              type="checkbox"
              name="needs_verification"
              value="true"
              defaultChecked={filters.needs_verification === "true"}
            />
            Needs verification
          </label>
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
        {views.ok ? (
          <SavedViews
            workspaceId={workspaceId}
            page="responsibilities"
            base={base}
            views={views.data}
            current={filtered ? currentQuery : ""}
          />
        ) : null}

        {list.data.length === 0 ? (
          <EmptyState
            title={filtered ? "No matching responsibilities" : "No responsibilities yet"}
            description={
              filtered
                ? "Try a different search or clear the filters."
                : "Record the ongoing work your organisation depends on, then assign owners and backups."
            }
            action={
              !filtered && manage ? (
                <Link href={`${base}/new`} className={buttonVariants({ size: "sm" })}>
                  Add the first one
                </Link>
              ) : undefined
            }
          />
        ) : (
          <div className="overflow-x-auto rounded-lg border">
            <table className="w-full text-sm">
              <thead className="text-muted-foreground bg-muted/40 text-left text-xs">
                <tr>
                  <th className="px-4 py-2 font-medium">Name</th>
                  <th className="px-4 py-2 font-medium">Criticality</th>
                  <th className="px-4 py-2 font-medium">Primary owner</th>
                  <th className="px-4 py-2 font-medium">Backups</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {list.data.map((r) => (
                  <tr key={r.id} className="hover:bg-muted/40">
                    <td className="px-4 py-2.5">
                      <Link href={`${base}/${r.id}`} className="font-medium hover:underline">
                        {r.name}
                      </Link>
                      {r.type_name || r.category ? (
                        <span className="text-muted-foreground ml-2 text-xs">
                          {r.type_name ?? r.category}
                        </span>
                      ) : null}
                      {r.restricted ? (
                        <Badge tone="muted" className="ml-2">
                          Restricted
                        </Badge>
                      ) : null}
                      {r.needs_verification ? (
                        <Badge tone="warning" className="ml-2">
                          Verify
                        </Badge>
                      ) : null}
                      {r.review_due ? (
                        <Badge tone="warning" className="ml-2">
                          Review due
                        </Badge>
                      ) : null}
                    </td>
                    <td className="px-4 py-2.5">
                      <CriticalityBadge value={r.criticality} />
                    </td>
                    <td className="px-4 py-2.5">
                      {r.primary_owner ? (
                        <>
                          {r.primary_owner.name}
                          {r.primary_owner.department_name ? (
                            <span className="text-muted-foreground ml-2 text-xs">
                              {r.primary_owner.department_name}
                            </span>
                          ) : null}
                        </>
                      ) : (
                        <Badge tone="warning">Unowned</Badge>
                      )}
                    </td>
                    <td className="px-4 py-2.5 tabular-nums">
                      {r.backup_count > 0 ? (
                        r.backup_count
                      ) : (
                        <span className="text-muted-foreground">None</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <PageNav base={base} query={filters} after={after} next={list.data.nextCursor} />
      </div>
    </div>
  );
}
