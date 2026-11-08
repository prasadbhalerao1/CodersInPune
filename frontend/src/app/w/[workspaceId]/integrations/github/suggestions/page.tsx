import Link from "next/link";

import { ActionForm, inputClass } from "@/components/action-form";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { EmptyState, PageHeader } from "@/components/page";
import { Badge, ROLE_LABEL } from "@/components/ui/badge";
import { attempt } from "@/lib/attempt";
import { api } from "@/lib/relay-api";
import { cn } from "@/lib/utils";

import { decideSuggestionAction } from "../../actions";
import { GitHubTabs } from "../tabs";
import { BULK_FORM, BulkBar } from "./bulk-bar";

const TABS = ["open", "deferred", "dismissed", "approved"] as const;
const SOURCE: Record<string, string> = {
  codeowners: "CODEOWNERS",
  catalog_info: "Backstage",
  maintainer: "Maintainer",
  activity: "Activity",
};

export default async function SuggestionsPage({
  params,
  searchParams,
}: PageProps<"/w/[workspaceId]/integrations/github/suggestions">) {
  const [{ workspaceId }, query] = await Promise.all([params, searchParams]);
  const tab = TABS.find((t) => t === query.status) ?? "open";
  const [suggestions, people, teams] = await Promise.all([
    attempt(api.githubSuggestions(workspaceId, tab)),
    attempt(api.listPeople(workspaceId)),
    attempt(api.listTeams(workspaceId)),
  ]);
  if (!suggestions.ok) return <ApiErrorNotice error={suggestions.error} />;
  if (!people.ok) return <ApiErrorNotice error={people.error} />;
  if (!teams.ok) return <ApiErrorNotice error={teams.error} />;
  const base = `/w/${workspaceId}/integrations/github/suggestions`;
  const actionable = tab === "open" || tab === "deferred";

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader title="GitHub" />
      <GitHubTabs workspaceId={workspaceId} current="suggestions" />
      <div className="flex flex-col gap-4 p-6">
        <p className="text-muted-foreground max-w-prose text-sm">
          Proposed from GitHub evidence. Approving records the owner through the normal ownership
          history; an existing primary owner is never replaced.
        </p>
        <nav aria-label="Status" className="flex gap-1 text-sm">
          {TABS.map((t) => (
            <Link
              key={t}
              href={t === "open" ? base : `${base}?status=${t}`}
              aria-current={tab === t ? "page" : undefined}
              className={cn(
                "rounded-md px-2.5 py-1 capitalize",
                tab === t
                  ? "bg-foreground/[0.06] font-medium"
                  : "text-muted-foreground hover:bg-muted",
              )}
            >
              {t}
            </Link>
          ))}
        </nav>
        {suggestions.data.length === 0 ? (
          <EmptyState
            title={`No ${tab} suggestions`}
            description="Suggestions appear after GitHub syncs repositories with CODEOWNERS, catalog files or maintainers."
          />
        ) : (
          <>
            {actionable ? (
              <BulkBar
                workspaceId={workspaceId}
                actions={tab === "open" ? ["approve", "defer", "dismiss"] : ["approve", "dismiss"]}
              />
            ) : null}
            <ul className="divide-y rounded-lg border">
              {suggestions.data.map((s) => (
                <li
                  key={s.id}
                  className="flex flex-col gap-3 px-4 py-3 text-sm lg:flex-row lg:items-start"
                >
                  {actionable ? (
                    <input
                      type="checkbox"
                      name="ids"
                      value={s.id}
                      form={BULK_FORM}
                      aria-label={`Select ${s.handle} for ${s.repository}`}
                      className="mt-1 size-4 shrink-0"
                    />
                  ) : null}
                  <div className="min-w-0 flex-1">
                    <p>
                      <span className="font-mono text-[13px] font-medium">{s.handle}</span>
                      <span className="text-muted-foreground mx-1.5">→</span>
                      <span>{ROLE_LABEL[s.proposed_role]}</span>
                      <span className="text-muted-foreground"> of </span>
                      <a
                        href={s.repository_url}
                        target="_blank"
                        rel="noreferrer"
                        className="font-medium hover:underline"
                      >
                        {s.repository}
                      </a>
                    </p>
                    <p className="text-muted-foreground text-xs">{s.reason}</p>
                    <ul className="mt-1.5 flex flex-col gap-1">
                      {s.evidence.map((e, i) => (
                        <li key={i} className="flex items-center gap-2 text-xs">
                          <Badge tone="muted">{SOURCE[e.source] ?? e.source}</Badge>
                          {e.url ? (
                            <a
                              href={e.url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-muted-foreground truncate hover:underline"
                            >
                              {e.detail} ↗
                            </a>
                          ) : (
                            <code className="text-muted-foreground truncate">{e.detail}</code>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                  {actionable ? (
                    <ActionForm
                      action={decideSuggestionAction.bind(null, workspaceId, s.id)}
                      className="flex-row flex-wrap items-center gap-2 lg:w-[30rem] lg:justify-end"
                    >
                      <select
                        name="assignee"
                        defaultValue={s.match ? `${s.match.type}:${s.match.id}` : ""}
                        aria-label="Owner"
                        className={`${inputClass} h-8 w-44`}
                      >
                        <option value="">{s.match ? "Matched owner" : "Choose owner…"}</option>
                        <optgroup label="Teams">
                          {teams.data.map((t) => (
                            <option key={t.id} value={`team:${t.id}`}>
                              {t.name}
                            </option>
                          ))}
                        </optgroup>
                        <optgroup label="People">
                          {people.data.map((p) => (
                            <option key={p.id} value={`person:${p.id}`}>
                              {p.display_name}
                            </option>
                          ))}
                        </optgroup>
                      </select>
                      <select
                        name="role"
                        defaultValue={s.proposed_role}
                        aria-label="Role"
                        className={`${inputClass} h-8 w-28`}
                      >
                        <option value="primary">Primary</option>
                        <option value="co_owner">Co-owner</option>
                        <option value="backup">Backup</option>
                      </select>
                      <button
                        type="submit"
                        name="action"
                        value="approve"
                        className="bg-primary text-primary-foreground h-8 rounded-lg px-3 text-sm font-medium"
                      >
                        Approve
                      </button>
                      {tab === "open" ? (
                        <button
                          type="submit"
                          name="action"
                          value="defer"
                          className="hover:bg-muted h-8 rounded-lg px-2 text-sm"
                        >
                          Later
                        </button>
                      ) : null}
                      <button
                        type="submit"
                        name="action"
                        value="dismiss"
                        className="hover:bg-muted text-muted-foreground h-8 rounded-lg px-2 text-sm"
                      >
                        Dismiss
                      </button>
                    </ActionForm>
                  ) : tab === "dismissed" ? (
                    <ActionForm action={decideSuggestionAction.bind(null, workspaceId, s.id)}>
                      <button
                        type="submit"
                        name="action"
                        value="reopen"
                        className="hover:bg-muted h-8 rounded-lg border px-3 text-sm"
                      >
                        Reopen
                      </button>
                    </ActionForm>
                  ) : null}
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    </div>
  );
}
