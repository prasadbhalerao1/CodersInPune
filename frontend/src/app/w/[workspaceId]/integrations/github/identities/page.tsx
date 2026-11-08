import Link from "next/link";

import { ActionForm, inputClass, SubmitButton } from "@/components/action-form";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { EmptyState, PageHeader } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { attempt } from "@/lib/attempt";
import { api } from "@/lib/relay-api";
import type { IdentityView, PersonView } from "@/lib/types";
import { cn } from "@/lib/utils";

import { decideIdentityAction } from "../../actions";
import { GitHubTabs } from "../tabs";

const FILTERS = [
  { key: "review", label: "Needs review" },
  { key: "linked", label: "Linked" },
  { key: "dismissed", label: "Dismissed" },
] as const;

function IdentityRow({
  workspaceId,
  identity: i,
  people,
}: {
  workspaceId: string;
  identity: IdentityView;
  people: PersonView[];
}) {
  const decide = (action: "link" | "unlink" | "dismiss" | "create_person") =>
    decideIdentityAction.bind(null, workspaceId, i.id, action);
  return (
    <li className="flex flex-col gap-3 px-4 py-3 text-sm lg:flex-row lg:items-center">
      <div className="min-w-0 flex-1">
        <p className="flex flex-wrap items-center gap-2">
          <a
            href={i.profile_url}
            target="_blank"
            rel="noreferrer"
            className="font-mono text-[13px] font-medium hover:underline"
          >
            @{i.login}
          </a>
          {i.name ? <span className="text-muted-foreground">{i.name}</span> : null}
          {i.link_status === "suggested" ? <Badge tone="warning">Suggested match</Badge> : null}
        </p>
        <p className="text-muted-foreground text-xs">
          {[
            i.person ? `Linked to ${i.person.name}` : null,
            i.suggested_person
              ? `Possibly ${i.suggested_person.name}: ${i.match_reason}`
              : i.match_reason,
            i.teams.length ? i.teams.join(", ") : null,
            i.recent_items ? `${i.recent_items} recent pull requests or issues` : null,
          ]
            .filter(Boolean)
            .join(" · ") || "Seen in repository activity"}
        </p>
      </div>
      {i.link_status === "linked" ? (
        <ActionForm action={decide("unlink")}>
          <SubmitButton size="sm" variant="ghost" pendingLabel="…">
            Unlink
          </SubmitButton>
        </ActionForm>
      ) : i.link_status === "dismissed" ? null : (
        <div className="flex flex-wrap items-center gap-2">
          <ActionForm action={decide("link")} className="flex-row items-center gap-2">
            <select
              name="person_id"
              defaultValue={i.suggested_person?.id ?? ""}
              aria-label={`Person for @${i.login}`}
              className={cn(inputClass, "h-8 w-48")}
            >
              <option value="">Choose person…</option>
              {people.map((p) => (
                <option key={p.id} value={p.id} disabled={Boolean(p.github_login)}>
                  {p.display_name}
                  {p.github_login ? ` (@${p.github_login})` : ""}
                </option>
              ))}
            </select>
            <SubmitButton size="sm" variant={i.suggested_person ? "default" : "outline"}>
              {i.suggested_person ? "Confirm" : "Link"}
            </SubmitButton>
          </ActionForm>
          <ActionForm action={decide("create_person")}>
            <SubmitButton size="sm" variant="ghost" pendingLabel="…">
              New person
            </SubmitButton>
          </ActionForm>
          <ActionForm action={decide("dismiss")}>
            <SubmitButton size="sm" variant="ghost" pendingLabel="…">
              Not ours
            </SubmitButton>
          </ActionForm>
        </div>
      )}
    </li>
  );
}

export default async function IdentitiesPage({
  params,
  searchParams,
}: PageProps<"/w/[workspaceId]/integrations/github/identities">) {
  const [{ workspaceId }, query] = await Promise.all([params, searchParams]);
  const filter = FILTERS.find((f) => f.key === query.status)?.key ?? "review";
  const [identities, people] = await Promise.all([
    attempt(api.githubIdentities(workspaceId, filter)),
    attempt(api.listPeople(workspaceId)),
  ]);
  if (!identities.ok) return <ApiErrorNotice error={identities.error} />;
  if (!people.ok) return <ApiErrorNotice error={people.error} />;
  const base = `/w/${workspaceId}/integrations/github/identities`;

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader title="GitHub" />
      <GitHubTabs workspaceId={workspaceId} current="identities" />
      <div className="flex max-w-5xl flex-col gap-4 p-6">
        <p className="text-muted-foreground max-w-prose text-sm">
          GitHub users seen in your repositories. Linking tells Relay who a handle is, so evidence
          and suggestions name real people. Matches are only suggested; nothing is linked or merged
          until you confirm.
        </p>
        <nav aria-label="Filter" className="flex gap-1 text-sm">
          {FILTERS.map((f) => (
            <Link
              key={f.key}
              href={f.key === "review" ? base : `${base}?status=${f.key}`}
              aria-current={filter === f.key ? "page" : undefined}
              className={cn(
                "rounded-md px-2.5 py-1",
                filter === f.key
                  ? "bg-foreground/[0.06] font-medium"
                  : "text-muted-foreground hover:bg-muted",
              )}
            >
              {f.label}
            </Link>
          ))}
        </nav>
        {identities.data.length === 0 ? (
          <EmptyState
            title={filter === "review" ? "Nothing to review" : `No ${filter} identities`}
            description="Identities appear after GitHub syncs collaborators, teams and pull request activity."
          />
        ) : (
          <ul className="divide-y rounded-lg border">
            {identities.data.map((i) => (
              <IdentityRow key={i.id} workspaceId={workspaceId} identity={i} people={people.data} />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
