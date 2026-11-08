import { ActionForm, inputClass, SubmitButton } from "@/components/action-form";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { EmptyState, PageHeader } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { attempt } from "@/lib/attempt";
import { api } from "@/lib/relay-api";
import { cn } from "@/lib/utils";

import { linkTeamAction } from "../../actions";
import { GitHubTabs } from "../tabs";

export default async function GitHubTeamsPage({
  params,
}: PageProps<"/w/[workspaceId]/integrations/github/teams">) {
  const { workspaceId } = await params;
  const [teams, relayTeams] = await Promise.all([
    attempt(api.githubTeams(workspaceId)),
    attempt(api.listTeams(workspaceId)),
  ]);
  if (!teams.ok) return <ApiErrorNotice error={teams.error} />;
  if (!relayTeams.ok) return <ApiErrorNotice error={relayTeams.error} />;
  const unlinked = relayTeams.data.filter((t) => !t.github_slug);

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader title="GitHub" />
      <GitHubTabs workspaceId={workspaceId} current="teams" />
      <div className="flex max-w-5xl flex-col gap-4 p-6">
        <p className="text-muted-foreground max-w-prose text-sm">
          Teams from connected GitHub organisations. Link one to a Relay team so CODEOWNERS entries
          like <code className="text-xs">@org/team</code> match it. Linking adds the team&apos;s
          linked people to the Relay team and never removes anyone.
        </p>
        {teams.data.length === 0 ? (
          <EmptyState
            title="No GitHub teams"
            description="Teams sync from organisation installations once the app has 'Organization > Members: Read-only'. Personal accounts have no teams."
          />
        ) : (
          <ul className="divide-y rounded-lg border">
            {teams.data.map((t) => (
              <li
                key={t.id}
                className={cn(
                  "flex flex-col gap-3 px-4 py-3 text-sm lg:flex-row lg:items-start",
                  t.removed && "opacity-60",
                )}
              >
                <div className="min-w-0 flex-1">
                  <p className="flex items-center gap-2">
                    <span className="font-mono text-[13px] font-medium">
                      @{t.org}/{t.slug}
                    </span>
                    {t.removed ? <Badge tone="muted">Removed on GitHub</Badge> : null}
                    {t.linked_team ? (
                      <span className="text-muted-foreground text-xs">→ {t.linked_team.name}</span>
                    ) : null}
                  </p>
                  <ul className="mt-1.5 flex flex-wrap gap-1">
                    {t.members.length === 0 ? (
                      <li className="text-muted-foreground text-xs">No members</li>
                    ) : (
                      t.members.map((m) => (
                        <li
                          key={m.login}
                          className={cn(
                            "rounded px-1.5 py-0.5 text-xs",
                            m.person ? "bg-muted" : "text-muted-foreground border border-dashed",
                          )}
                          title={m.person ? `Linked to ${m.person.name}` : "Not linked to a person"}
                        >
                          {m.person?.name ?? `@${m.login}`}
                        </li>
                      ))
                    )}
                  </ul>
                </div>
                {t.linked_team ? (
                  <ActionForm action={linkTeamAction.bind(null, workspaceId, t.id, "unlink")}>
                    <SubmitButton size="sm" variant="ghost" pendingLabel="…">
                      Unlink
                    </SubmitButton>
                  </ActionForm>
                ) : t.removed ? null : (
                  <div className="flex flex-wrap items-center gap-2">
                    <ActionForm action={linkTeamAction.bind(null, workspaceId, t.id, "create")}>
                      <SubmitButton size="sm" variant="outline">
                        Create Relay team
                      </SubmitButton>
                    </ActionForm>
                    {unlinked.length > 0 ? (
                      <ActionForm
                        action={linkTeamAction.bind(null, workspaceId, t.id, "link")}
                        className="flex-row items-center gap-2"
                      >
                        <select
                          name="team_id"
                          defaultValue=""
                          aria-label={`Relay team for @${t.org}/${t.slug}`}
                          className={cn(inputClass, "h-8 w-44")}
                        >
                          <option value="">Link to existing…</option>
                          {unlinked.map((rt) => (
                            <option key={rt.id} value={rt.id}>
                              {rt.name}
                            </option>
                          ))}
                        </select>
                        <SubmitButton size="sm" variant="ghost">
                          Link
                        </SubmitButton>
                      </ActionForm>
                    ) : null}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
