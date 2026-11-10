import type { Metadata } from "next";
import Link from "next/link";

import { ApiErrorNotice } from "@/components/api-error-notice";
import { PageHeader, Section } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { attempt } from "@/lib/attempt";
import { api, canManage } from "@/lib/relay-api";
import { cn } from "@/lib/utils";

import { SettingsNav } from "../settings-nav";

export const metadata: Metadata = { title: "Roles & access" };

const ROLE_LABEL: Record<string, string> = {
  owner: "Owner",
  admin: "Admin",
  continuity_manager: "Continuity manager",
  knowledge_steward: "Knowledge steward",
  team_manager: "Team manager",
  member: "Member",
  auditor: "Auditor",
  guest: "Guest",
};
const ORDER = Object.keys(ROLE_LABEL);

/** "responsibility.manage" -> "Responsibility · manage" */
const permissionLabel = (p: string) => {
  const [area, verb] = p.split(".");
  return `${area[0].toUpperCase()}${area.slice(1)} · ${verb}`;
};

export default async function RolesPage({ params }: PageProps<"/w/[workspaceId]/settings/roles">) {
  const { workspaceId } = await params;
  const [workspace, roles] = await Promise.all([
    attempt(api.getWorkspace(workspaceId)),
    attempt(api.roles(workspaceId)),
  ]);
  if (!workspace.ok) return <ApiErrorNotice error={workspace.error} />;
  if (!roles.ok) return <ApiErrorNotice error={roles.error} />;
  const admin = canManage(workspace.data);
  const conflicts = admin ? await attempt(api.identityConflicts(workspaceId)) : null;
  const sorted = [...roles.data].sort((a, b) => ORDER.indexOf(a.role) - ORDER.indexOf(b.role));
  const permissions = [...new Set(sorted.flatMap((r) => r.permissions))].sort();

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader title="Settings" />
      <SettingsNav workspaceId={workspaceId} current="roles" admin={admin} />
      <div className="flex max-w-6xl flex-col gap-8 p-6">
        <Section
          title="Roles and permissions"
          description="Every role and exactly what it allows. Change someone's role on the Members page."
          aside={
            <Link
              href={`/w/${workspaceId}/members`}
              className="text-sm underline-offset-2 hover:underline"
            >
              Members →
            </Link>
          }
        >
          <ul className="grid gap-3 sm:grid-cols-2">
            {sorted.map((r) => (
              <li key={r.role} className="rounded-lg border p-3 text-sm">
                <p className="font-medium">{ROLE_LABEL[r.role] ?? r.role}</p>
                <p className="text-muted-foreground text-xs">{r.description}</p>
              </li>
            ))}
          </ul>
          <div className="overflow-x-auto rounded-lg border">
            <table className="w-full text-xs">
              <thead className="bg-muted/40 text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 text-left font-medium">Permission</th>
                  {sorted.map((r) => (
                    <th key={r.role} className="px-2 py-2 font-medium whitespace-nowrap">
                      {ROLE_LABEL[r.role] ?? r.role}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y">
                {permissions.map((p) => (
                  <tr key={p}>
                    <td className="px-3 py-1.5 whitespace-nowrap">{permissionLabel(p)}</td>
                    {sorted.map((r) => {
                      const has = r.permissions.includes(p);
                      return (
                        <td
                          key={r.role}
                          className={cn(
                            "px-2 py-1.5 text-center",
                            !has && "text-muted-foreground/40",
                          )}
                          aria-label={`${ROLE_LABEL[r.role]} ${has ? "can" : "cannot"} ${p}`}
                        >
                          {has ? "✓" : "·"}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-muted-foreground text-xs">
            Team managers manage only responsibilities held by their teams (or the teams&apos;
            members). Restricted responsibilities stay hidden from everyone but owners, admins,
            current holders and people granted access.
          </p>
        </Section>

        {conflicts ? (
          <Section
            title="Identity review"
            description="Where GitHub, Linear and the directory disagree about who someone is. Nothing is merged automatically."
          >
            {!conflicts.ok ? (
              <ApiErrorNotice error={conflicts.error} />
            ) : conflicts.data.length === 0 ? (
              <p className="text-muted-foreground text-sm">No conflicts.</p>
            ) : (
              <ul className="divide-y rounded-lg border text-sm">
                {conflicts.data.map((c, i) => (
                  <li key={i} className="flex flex-wrap items-center gap-2 px-4 py-2.5">
                    <Badge tone={c.kind === "pending_match" ? "muted" : "warning"}>
                      {c.provider}
                    </Badge>
                    <span className="font-medium">{c.handle}</span>
                    {c.person_id ? (
                      <Link
                        href={`/w/${workspaceId}/people/${c.person_id}`}
                        className="underline-offset-2 hover:underline"
                      >
                        {c.person_name}
                      </Link>
                    ) : null}
                    <span className="text-muted-foreground w-full text-xs">{c.detail}</span>
                  </li>
                ))}
              </ul>
            )}
            <p className="text-muted-foreground text-xs">
              Resolve matches in{" "}
              <Link href={`/w/${workspaceId}/integrations/github/identities`} className="underline">
                GitHub identities
              </Link>{" "}
              and the Linear integration page.
            </p>
          </Section>
        ) : null}
      </div>
    </div>
  );
}
