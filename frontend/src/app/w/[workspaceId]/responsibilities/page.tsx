import Link from "next/link";

import { inputClass } from "@/components/action-form";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { EmptyState, PageHeader } from "@/components/page";
import { Badge, CriticalityBadge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { attempt } from "@/lib/attempt";
import { api, canManage } from "@/lib/relay-api";

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
  };
  const [workspace, list, departments] = await Promise.all([
    attempt(api.getWorkspace(workspaceId)),
    attempt(api.listResponsibilities(workspaceId, filters)),
    attempt(api.departments(workspaceId)),
  ]);
  if (!workspace.ok) return <ApiErrorNotice error={workspace.error} />;
  if (!list.ok) return <ApiErrorNotice error={list.error} />;
  const base = `/w/${workspaceId}/responsibilities`;
  const filtered = Boolean(
    filters.q || filters.criticality || filters.department_id || filters.status !== "active",
  );
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
                      {r.category ? (
                        <span className="text-muted-foreground ml-2 text-xs">{r.category}</span>
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
      </div>
    </div>
  );
}
