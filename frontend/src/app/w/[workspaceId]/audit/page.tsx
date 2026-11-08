import Link from "next/link";

import { inputClass } from "@/components/action-form";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { EmptyState, formatDateTime, PageHeader } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { attempt } from "@/lib/attempt";
import { api } from "@/lib/relay-api";
import type { AuditEventView } from "@/lib/types";

const CATEGORIES = [
  { value: "responsibility", label: "Responsibilities" },
  { value: "ownership", label: "Ownership" },
  { value: "case", label: "Cases" },
  { value: "risk", label: "Risks" },
  { value: "asset", label: "Assets" },
  { value: "person", label: "People" },
  { value: "team", label: "Teams" },
  { value: "department", label: "Departments" },
  { value: "membership", label: "Members" },
  { value: "invitation", label: "Invitations" },
  { value: "integration", label: "Integrations" },
  { value: "import", label: "Imports" },
  { value: "authorization", label: "Access denied" },
  { value: "job", label: "Background jobs" },
] as const;

const TARGET_PATH: Record<string, string> = {
  responsibility: "responsibilities",
  continuity_case: "cases",
  asset: "assets",
};

const PAGE = 100;

function humanize(action: string): string {
  const [, verb = action] = action.split(/\.(.+)/);
  return verb.replaceAll("_", " ").replaceAll(".", " · ");
}

function Target({ event, workspaceId }: { event: AuditEventView; workspaceId: string }) {
  if (!event.target_type) return <span className="text-muted-foreground">—</span>;
  const label = event.target_label ?? event.target_type.replaceAll("_", " ");
  const path = TARGET_PATH[event.target_type];
  return path && event.target_id ? (
    <Link href={`/w/${workspaceId}/${path}/${event.target_id}`} className="hover:underline">
      {label}
    </Link>
  ) : (
    <span>{label}</span>
  );
}

export default async function AuditPage({
  params,
  searchParams,
}: PageProps<"/w/[workspaceId]/audit">) {
  const [{ workspaceId }, query] = await Promise.all([params, searchParams]);
  const pick = (key: string) => (typeof query[key] === "string" ? query[key] : undefined);
  const filters = {
    category: pick("category"),
    actor_user_id: pick("actor"),
    before: pick("before"),
    limit: String(PAGE),
  };
  const [events, members] = await Promise.all([
    attempt(api.auditEvents(workspaceId, filters)),
    attempt(api.members(workspaceId, { include_inactive: "true" })),
  ]);
  if (!events.ok) return <ApiErrorNotice error={events.error} />;
  const base = `/w/${workspaceId}/audit`;
  const keep = new URLSearchParams(
    Object.entries({ category: filters.category, actor: filters.actor_user_id }).filter(
      (e): e is [string, string] => Boolean(e[1]),
    ),
  );
  const last = events.data.at(-1);
  const older = last
    ? `${base}?${new URLSearchParams([...keep, ["before", last.occurred_at]])}`
    : null;

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader title="Audit log" />
      <div className="flex flex-col gap-4 p-6">
        <p className="text-muted-foreground max-w-prose text-sm">
          Every change, decision and denied access, in order. Entries cannot be edited or deleted,
          and they record identifiers only, never the content people wrote.
        </p>
        <form className="flex flex-wrap gap-2" role="search">
          <select
            name="category"
            defaultValue={filters.category ?? ""}
            aria-label="Category"
            className={`${inputClass} w-48`}
          >
            <option value="">All activity</option>
            {CATEGORIES.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
          {members.ok ? (
            <select
              name="actor"
              defaultValue={filters.actor_user_id ?? ""}
              aria-label="Person"
              className={`${inputClass} w-52`}
            >
              <option value="">Anyone</option>
              {members.data.map((m) => (
                <option key={m.user_id} value={m.user_id}>
                  {m.name}
                </option>
              ))}
            </select>
          ) : null}
          <button type="submit" className={buttonVariants({ variant: "outline" })}>
            Apply
          </button>
          {filters.category || filters.actor_user_id || filters.before ? (
            <Link href={base} className={buttonVariants({ variant: "ghost" })}>
              Latest
            </Link>
          ) : null}
        </form>

        {events.data.length === 0 ? (
          <EmptyState title="No matching activity" description="Try another category or person." />
        ) : (
          <div className="overflow-x-auto rounded-lg border">
            <table className="w-full text-sm">
              <thead className="text-muted-foreground bg-muted/40 text-left text-xs">
                <tr>
                  <th className="w-44 px-4 py-2 font-medium">When</th>
                  <th className="px-4 py-2 font-medium">Who</th>
                  <th className="px-4 py-2 font-medium">What</th>
                  <th className="px-4 py-2 font-medium">On</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {events.data.map((e) => (
                  <tr key={e.id} className="align-top">
                    <td className="text-muted-foreground px-4 py-2 text-xs whitespace-nowrap tabular-nums">
                      {formatDateTime(e.occurred_at)}
                    </td>
                    <td className="px-4 py-2">
                      {e.actor_type === "system" ? (
                        <Badge tone="muted">Relay</Badge>
                      ) : (
                        (e.actor_name ?? "Member")
                      )}
                    </td>
                    <td className="px-4 py-2">
                      <span className="text-muted-foreground text-xs">
                        {e.action.split(".")[0].replaceAll("_", " ")}
                      </span>{" "}
                      <span
                        className={
                          e.action.startsWith("authorization.")
                            ? "text-red-700 dark:text-red-400"
                            : undefined
                        }
                      >
                        {humanize(e.action)}
                      </span>
                    </td>
                    <td className="px-4 py-2">
                      <Target event={e} workspaceId={workspaceId} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {older && events.data.length === PAGE ? (
          <Link
            href={older}
            className={`${buttonVariants({ variant: "outline", size: "sm" })} self-start`}
          >
            Older entries
          </Link>
        ) : null}
      </div>
    </div>
  );
}
