import { ActionForm, Field, inputClass, SubmitButton } from "@/components/action-form";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { formatDateTime, PageHeader, Section } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { attempt } from "@/lib/attempt";
import { api, canManage, isOwner } from "@/lib/relay-api";
import type { WorkspaceRole } from "@/lib/types";

import { inviteMemberAction, revokeInvitationAction, updateMemberAction } from "./actions";

const ROLES: { value: WorkspaceRole; label: string; hint: string }[] = [
  { value: "owner", label: "Owner", hint: "Everything, including other owners" },
  { value: "admin", label: "Admin", hint: "Manage members, catalogue, cases and integrations" },
  { value: "member", label: "Member", hint: "Read and work on assigned tasks" },
  { value: "auditor", label: "Auditor", hint: "Read-only, including the audit log" },
  { value: "guest", label: "Guest", hint: "Read-only" },
];

export default async function MembersPage({ params }: PageProps<"/w/[workspaceId]/members">) {
  const { workspaceId } = await params;
  const [workspace, members] = await Promise.all([
    attempt(api.getWorkspace(workspaceId)),
    attempt(api.members(workspaceId, { include_inactive: "true" })),
  ]);
  if (!workspace.ok) return <ApiErrorNotice error={workspace.error} />;
  if (!members.ok) return <ApiErrorNotice error={members.error} />;
  const manage = canManage(workspace.data);
  const owner = isOwner(workspace.data);
  const invitations = manage ? await attempt(api.invitations(workspaceId)) : null;
  if (invitations && !invitations.ok) return <ApiErrorNotice error={invitations.error} />;
  const roles = owner ? ROLES : ROLES.filter((r) => r.value !== "owner");

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader title="Members" />
      <div className="flex max-w-4xl flex-col gap-8 p-6">
        {manage ? (
          <Section
            title="Invite someone"
            description="They receive an email and join after signing in with that address."
          >
            <ActionForm
              action={inviteMemberAction.bind(null, workspaceId)}
              className="flex-row flex-wrap items-end gap-2 rounded-lg border p-4"
            >
              <Field label="Email" htmlFor="invite-email">
                <input
                  id="invite-email"
                  name="email"
                  type="email"
                  required
                  maxLength={320}
                  placeholder="name@company.com"
                  className={`${inputClass} min-w-72`}
                />
              </Field>
              <Field label="Role" htmlFor="invite-role">
                <select id="invite-role" name="role" defaultValue="member" className={inputClass}>
                  {roles.map((r) => (
                    <option key={r.value} value={r.value} title={r.hint}>
                      {r.label}
                    </option>
                  ))}
                </select>
              </Field>
              <SubmitButton size="sm">Send invitation</SubmitButton>
            </ActionForm>
          </Section>
        ) : null}

        {invitations?.ok && invitations.data.length > 0 ? (
          <Section title="Pending invitations">
            <ul className="divide-y rounded-lg border">
              {invitations.data.map((i) => (
                <li key={i.id} className="flex items-center gap-3 px-4 py-2.5 text-sm">
                  <span className="min-w-0 flex-1 truncate">{i.email}</span>
                  <span className="text-muted-foreground text-xs capitalize">{i.role}</span>
                  {i.expired ? (
                    <Badge tone="warning">Expired</Badge>
                  ) : (
                    <span className="text-muted-foreground text-xs">
                      Expires {formatDateTime(i.expires_at)}
                    </span>
                  )}
                  {i.email_sent ? null : <Badge tone="muted">Email not sent</Badge>}
                  <ActionForm action={revokeInvitationAction.bind(null, workspaceId, i.id)}>
                    <SubmitButton
                      size="sm"
                      variant="ghost"
                      pendingLabel="…"
                      confirm="Revoke this invitation? The link stops working."
                    >
                      Revoke
                    </SubmitButton>
                  </ActionForm>
                </li>
              ))}
            </ul>
          </Section>
        ) : null}

        <Section
          title="People with access"
          description={`${members.data.filter((m) => m.status === "active").length} active`}
        >
          <div className="overflow-x-auto rounded-lg border">
            <table className="w-full text-sm">
              <thead className="text-muted-foreground bg-muted/40 text-left text-xs">
                <tr>
                  <th className="px-4 py-2 font-medium">Member</th>
                  <th className="px-4 py-2 font-medium">Role</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                  {manage ? <th className="px-4 py-2" /> : null}
                </tr>
              </thead>
              <tbody className="divide-y">
                {members.data.map((m) => {
                  const editable = manage && (owner || m.role !== "owner");
                  return (
                    <tr key={m.user_id}>
                      <td className="px-4 py-2.5">
                        <span className="font-medium">{m.name}</span>
                        {m.email && m.email !== m.name ? (
                          <span className="text-muted-foreground block text-xs">{m.email}</span>
                        ) : null}
                      </td>
                      <td className="px-4 py-2.5 capitalize">{m.role}</td>
                      <td className="px-4 py-2.5">
                        {m.status === "active" ? (
                          <span className="text-muted-foreground text-xs">Active</span>
                        ) : (
                          <Badge tone="warning">{m.status}</Badge>
                        )}
                      </td>
                      {manage ? (
                        <td className="px-4 py-2">
                          {editable ? (
                            <ActionForm
                              action={updateMemberAction.bind(null, workspaceId, m.user_id)}
                              className="flex-row items-center justify-end gap-2"
                            >
                              <select
                                name="role"
                                defaultValue={m.role}
                                aria-label={`Role for ${m.name}`}
                                className={`${inputClass} h-8 w-28`}
                              >
                                {roles.map((r) => (
                                  <option key={r.value} value={r.value}>
                                    {r.label}
                                  </option>
                                ))}
                              </select>
                              <select
                                name="status"
                                defaultValue={m.status}
                                aria-label={`Status for ${m.name}`}
                                className={`${inputClass} h-8 w-28`}
                              >
                                <option value="active">Active</option>
                                <option value="suspended">Suspended</option>
                                <option value="removed">Removed</option>
                              </select>
                              <SubmitButton size="sm" variant="outline" pendingLabel="…">
                                Save
                              </SubmitButton>
                            </ActionForm>
                          ) : null}
                        </td>
                      ) : null}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Section>
      </div>
    </div>
  );
}
