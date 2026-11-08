import { ActionForm, Field, inputClass, SubmitButton } from "@/components/action-form";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { EmptyState, PageHeader, Section } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { attempt } from "@/lib/attempt";
import { api, canManage } from "@/lib/relay-api";

import {
  addTeamMemberAction,
  createPersonAction,
  createTeamAction,
  removeTeamMemberAction,
  setPersonStatusAction,
} from "../actions";

export default async function PeoplePage({ params }: PageProps<"/w/[workspaceId]/people">) {
  const { workspaceId } = await params;
  const [workspace, people, teams] = await Promise.all([
    attempt(api.getWorkspace(workspaceId)),
    attempt(api.listPeople(workspaceId, { include_archived: "true" })),
    attempt(api.listTeams(workspaceId)),
  ]);
  if (!workspace.ok) return <ApiErrorNotice error={workspace.error} />;
  if (!people.ok) return <ApiErrorNotice error={people.error} />;
  if (!teams.ok) return <ApiErrorNotice error={teams.error} />;
  const manage = canManage(workspace.data);
  const activePeople = people.data.filter((p) => p.status === "active");

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader title="People & Teams" />
      <div className="grid gap-8 p-6 xl:grid-cols-2">
        <Section title="People" description="Directory entries; they don't need a Relay login.">
          {manage ? (
            <ActionForm
              action={createPersonAction.bind(null, workspaceId)}
              className="rounded-lg border p-4"
            >
              <div className="grid gap-3 sm:grid-cols-3">
                <Field label="Name" htmlFor="display_name">
                  <input
                    id="display_name"
                    name="display_name"
                    required
                    maxLength={200}
                    className={inputClass}
                  />
                </Field>
                <Field label="Email (optional)" htmlFor="email">
                  <input
                    id="email"
                    name="email"
                    type="email"
                    maxLength={320}
                    className={inputClass}
                  />
                </Field>
                <Field label="Title (optional)" htmlFor="title">
                  <input id="title" name="title" maxLength={200} className={inputClass} />
                </Field>
              </div>
              <div>
                <SubmitButton size="sm">Add person</SubmitButton>
              </div>
            </ActionForm>
          ) : null}
          {people.data.length === 0 ? (
            <EmptyState
              title="No people yet"
              description="Add the people who own or back up your responsibilities."
            />
          ) : (
            <ul className="divide-y rounded-lg border">
              {people.data.map((p) => (
                <li key={p.id} className="flex items-center gap-3 px-4 py-2.5 text-sm">
                  <span className="min-w-0 flex-1">
                    <span className="font-medium">{p.display_name}</span>
                    {p.status === "archived" ? (
                      <Badge tone="muted" className="ml-2">
                        Archived
                      </Badge>
                    ) : null}
                    <span className="text-muted-foreground block truncate text-xs">
                      {[p.title, p.email].filter(Boolean).join(" · ") || "—"}
                    </span>
                  </span>
                  {manage ? (
                    <ActionForm
                      action={setPersonStatusAction.bind(
                        null,
                        workspaceId,
                        p.id,
                        p.status === "active" ? "archived" : "active",
                      )}
                    >
                      <SubmitButton variant="ghost" size="sm" pendingLabel="…">
                        {p.status === "active" ? "Archive" : "Restore"}
                      </SubmitButton>
                    </ActionForm>
                  ) : null}
                </li>
              ))}
            </ul>
          )}
        </Section>

        <Section title="Teams" description="Teams can own responsibilities too.">
          {manage ? (
            <ActionForm
              action={createTeamAction.bind(null, workspaceId)}
              className="rounded-lg border p-4"
            >
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label="Team name" htmlFor="team-name">
                  <input
                    id="team-name"
                    name="name"
                    required
                    maxLength={200}
                    className={inputClass}
                  />
                </Field>
                <Field label="Description (optional)" htmlFor="team-description">
                  <input
                    id="team-description"
                    name="description"
                    maxLength={4000}
                    className={inputClass}
                  />
                </Field>
              </div>
              <div>
                <SubmitButton size="sm">Add team</SubmitButton>
              </div>
            </ActionForm>
          ) : null}
          {teams.data.length === 0 ? (
            <EmptyState
              title="No teams yet"
              description="Group people into teams to assign shared ownership."
            />
          ) : (
            <ul className="flex flex-col gap-3">
              {teams.data.map((t) => {
                const memberIds = new Set(t.members.map((m) => m.person_id));
                const candidates = activePeople.filter((p) => !memberIds.has(p.id));
                return (
                  <li key={t.id} className="rounded-lg border p-4">
                    <p className="text-sm font-medium">{t.name}</p>
                    {t.description ? (
                      <p className="text-muted-foreground text-xs">{t.description}</p>
                    ) : null}
                    <ul className="mt-3 flex flex-wrap gap-1.5">
                      {t.members.length === 0 ? (
                        <li className="text-muted-foreground text-xs">No members yet.</li>
                      ) : (
                        t.members.map((m) => (
                          <li
                            key={m.person_id}
                            className="bg-muted flex items-center gap-1 rounded-md py-0.5 pr-1 pl-2 text-xs"
                          >
                            {m.display_name}
                            {manage ? (
                              <ActionForm
                                action={removeTeamMemberAction.bind(
                                  null,
                                  workspaceId,
                                  t.id,
                                  m.person_id,
                                )}
                              >
                                <button
                                  type="submit"
                                  aria-label={`Remove ${m.display_name} from ${t.name}`}
                                  className="text-muted-foreground hover:text-foreground px-1"
                                >
                                  ×
                                </button>
                              </ActionForm>
                            ) : null}
                          </li>
                        ))
                      )}
                    </ul>
                    {manage && candidates.length > 0 ? (
                      <ActionForm
                        action={addTeamMemberAction.bind(null, workspaceId, t.id)}
                        className="mt-3 flex-row items-center gap-2"
                      >
                        <select
                          name="person_id"
                          aria-label={`Add a person to ${t.name}`}
                          defaultValue=""
                          className={`${inputClass} max-w-xs`}
                        >
                          <option value="" disabled>
                            Add a member…
                          </option>
                          {candidates.map((p) => (
                            <option key={p.id} value={p.id}>
                              {p.display_name}
                            </option>
                          ))}
                        </select>
                        <SubmitButton variant="outline" size="sm">
                          Add
                        </SubmitButton>
                      </ActionForm>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          )}
        </Section>
      </div>
    </div>
  );
}
