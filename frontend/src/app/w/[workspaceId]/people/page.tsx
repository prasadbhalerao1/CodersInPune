import Link from "next/link";

import { ActionForm, Field, inputClass, SubmitButton } from "@/components/action-form";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { EmptyState, PageHeader, Section } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { attempt } from "@/lib/attempt";
import { api, canManage } from "@/lib/relay-api";
import type { DepartmentView } from "@/lib/types";
import { cn } from "@/lib/utils";

import {
  addTeamMemberAction,
  createDepartmentAction,
  createPersonAction,
  createTeamAction,
  removeTeamMemberAction,
  setDepartmentAction,
  setDepartmentStatusAction,
  setPersonStatusAction,
} from "../actions";

function DepartmentSelect({
  departments,
  id,
  defaultValue = "",
  label,
}: {
  departments: DepartmentView[];
  id: string;
  defaultValue?: string;
  label?: string;
}) {
  return (
    <select
      id={id}
      name="department_id"
      defaultValue={defaultValue}
      aria-label={label}
      className={inputClass}
    >
      <option value="">No department</option>
      {departments.map((d) => (
        <option key={d.id} value={d.id}>
          {d.name}
        </option>
      ))}
    </select>
  );
}

export default async function PeoplePage({
  params,
  searchParams,
}: PageProps<"/w/[workspaceId]/people">) {
  const [{ workspaceId }, query] = await Promise.all([params, searchParams]);
  const department = typeof query.department === "string" ? query.department : undefined;
  const filter = department ? { department_id: department } : {};
  const [workspace, people, teams, departments] = await Promise.all([
    attempt(api.getWorkspace(workspaceId)),
    attempt(api.listPeople(workspaceId, { include_archived: "true", ...filter })),
    attempt(api.listTeams(workspaceId, filter)),
    attempt(api.departments(workspaceId)),
  ]);
  if (!workspace.ok) return <ApiErrorNotice error={workspace.error} />;
  if (!people.ok) return <ApiErrorNotice error={people.error} />;
  if (!teams.ok) return <ApiErrorNotice error={teams.error} />;
  if (!departments.ok) return <ApiErrorNotice error={departments.error} />;
  const manage = canManage(workspace.data);
  const activePeople = people.data.filter((p) => p.status === "active");
  const base = `/w/${workspaceId}/people`;
  const current = departments.data.find((d) => d.id === department);

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader title="People & Teams" />
      <div className="flex flex-col gap-8 p-6">
        <Section
          title="Departments"
          description="Group people and teams. Responsibilities follow their owners' departments."
          aside={
            manage ? (
              <ActionForm
                action={createDepartmentAction.bind(null, workspaceId)}
                className="flex-row items-center gap-2"
              >
                <input
                  name="name"
                  required
                  maxLength={200}
                  placeholder="New department"
                  aria-label="Department name"
                  className={cn(inputClass, "h-8 w-48")}
                />
                <SubmitButton size="sm" variant="outline">
                  Add
                </SubmitButton>
              </ActionForm>
            ) : null
          }
        >
          {departments.data.length === 0 ? (
            <p className="text-muted-foreground text-sm">
              No departments yet. They are optional; add them when your organisation needs them.
            </p>
          ) : (
            <nav aria-label="Filter by department" className="flex flex-wrap gap-1.5">
              <Link
                href={base}
                aria-current={!department ? "page" : undefined}
                className={cn(
                  "rounded-md border px-2.5 py-1 text-sm",
                  !department ? "bg-foreground/[0.06] font-medium" : "hover:bg-muted",
                )}
              >
                Everyone
              </Link>
              {departments.data.map((d) => (
                <Link
                  key={d.id}
                  href={`${base}?department=${d.id}`}
                  aria-current={department === d.id ? "page" : undefined}
                  className={cn(
                    "flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-sm",
                    department === d.id ? "bg-foreground/[0.06] font-medium" : "hover:bg-muted",
                  )}
                >
                  {d.name}
                  <span className="text-muted-foreground text-xs tabular-nums">
                    {d.people_count + d.team_count}
                  </span>
                </Link>
              ))}
            </nav>
          )}
          {current && manage ? (
            <div className="text-muted-foreground flex items-center gap-3 text-xs">
              <span>
                {current.people_count} people · {current.team_count} teams ·{" "}
                <Link
                  href={`/w/${workspaceId}/responsibilities?department_id=${current.id}`}
                  className="text-foreground underline"
                >
                  Responsibilities owned here
                </Link>
                {" · "}
                <Link
                  href={`/w/${workspaceId}/departments/${current.id}`}
                  className="text-foreground underline"
                >
                  Department overview
                </Link>
              </span>
              <ActionForm
                action={setDepartmentStatusAction.bind(null, workspaceId, current.id, "archived")}
              >
                <SubmitButton
                  variant="ghost"
                  size="sm"
                  pendingLabel="…"
                  confirm="Archive this department? People and teams keep their history."
                >
                  Archive department
                </SubmitButton>
              </ActionForm>
            </div>
          ) : null}
        </Section>

        <div className="grid gap-8 xl:grid-cols-2">
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
                  <Field label="Department" htmlFor="person-department">
                    <DepartmentSelect
                      id="person-department"
                      departments={departments.data}
                      defaultValue={department}
                    />
                  </Field>
                  <Field label="GitHub login" htmlFor="github_login">
                    <input
                      id="github_login"
                      name="github_login"
                      maxLength={39}
                      pattern="[A-Za-z0-9-]{1,39}"
                      placeholder="octocat"
                      className={inputClass}
                    />
                  </Field>
                </div>
                <div className="flex items-center justify-between">
                  <SubmitButton size="sm">Add person</SubmitButton>
                  <Link
                    href={`/w/${workspaceId}/import`}
                    className="text-muted-foreground text-xs hover:underline"
                  >
                    Import from CSV
                  </Link>
                </div>
              </ActionForm>
            ) : null}
            {people.data.length === 0 ? (
              <EmptyState
                title={current ? `Nobody in ${current.name}` : "No people yet"}
                description="Add the people who own or back up your responsibilities."
              />
            ) : (
              <ul className="divide-y rounded-lg border">
                {people.data.map((p) => (
                  <li key={p.id} className="flex items-center gap-3 px-4 py-2.5 text-sm">
                    <span className="min-w-0 flex-1">
                      <Link
                        href={`/w/${workspaceId}/people/${p.id}`}
                        className="font-medium hover:underline"
                      >
                        {p.display_name}
                      </Link>
                      {p.status === "archived" ? (
                        <Badge tone="muted" className="ml-2">
                          Archived
                        </Badge>
                      ) : null}
                      <span className="text-muted-foreground block truncate text-xs">
                        {[
                          p.title,
                          p.department_name,
                          p.email,
                          p.github_login && `@${p.github_login}`,
                        ]
                          .filter(Boolean)
                          .join(" · ") || "—"}
                      </span>
                    </span>
                    {manage && p.status === "active" && departments.data.length > 0 ? (
                      <ActionForm
                        action={setDepartmentAction.bind(null, workspaceId, "people", p.id)}
                        className="flex-row items-center gap-1"
                      >
                        <DepartmentSelect
                          id={`dept-${p.id}`}
                          label={`Department for ${p.display_name}`}
                          departments={departments.data}
                          defaultValue={p.department_id ?? ""}
                        />
                        <SubmitButton variant="ghost" size="sm" pendingLabel="…">
                          Set
                        </SubmitButton>
                      </ActionForm>
                    ) : null}
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
                  <Field label="Department" htmlFor="team-department">
                    <DepartmentSelect
                      id="team-department"
                      departments={departments.data}
                      defaultValue={department}
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
                  <Field label="GitHub team (org/slug)" htmlFor="team-github">
                    <input
                      id="team-github"
                      name="github_slug"
                      maxLength={140}
                      placeholder="acme/platform"
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
                title={current ? `No teams in ${current.name}` : "No teams yet"}
                description="Group people into teams to assign shared ownership."
              />
            ) : (
              <ul className="flex flex-col gap-3">
                {teams.data.map((t) => {
                  const memberIds = new Set(t.members.map((m) => m.person_id));
                  const candidates = activePeople.filter((p) => !memberIds.has(p.id));
                  return (
                    <li key={t.id} className="rounded-lg border p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <Link
                            href={`/w/${workspaceId}/teams/${t.id}`}
                            className="text-sm font-medium hover:underline"
                          >
                            {t.name}
                          </Link>
                          <p className="text-muted-foreground text-xs">
                            {[t.department_name, t.description].filter(Boolean).join(" · ") ||
                              "No department"}
                          </p>
                        </div>
                        {manage && departments.data.length > 0 ? (
                          <ActionForm
                            action={setDepartmentAction.bind(null, workspaceId, "teams", t.id)}
                            className="flex-row items-center gap-1"
                          >
                            <DepartmentSelect
                              id={`team-dept-${t.id}`}
                              label={`Department for ${t.name}`}
                              departments={departments.data}
                              defaultValue={t.department_id ?? ""}
                            />
                            <SubmitButton variant="ghost" size="sm" pendingLabel="…">
                              Set
                            </SubmitButton>
                          </ActionForm>
                        ) : null}
                      </div>
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
    </div>
  );
}
