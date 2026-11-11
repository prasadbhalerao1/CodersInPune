import { History } from "lucide-react";
import Link from "next/link";

import {
  ActionForm,
  DateTimeInput,
  Field,
  inputClass,
  SubmitButton,
} from "@/components/action-form";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { formatDateTime, PageHeader, Section } from "@/components/page";
import { Badge, CriticalityBadge, ROLE_LABEL, RoleBadge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { linkAssetAction, unlinkAssetAction } from "@/app/w/[workspaceId]/assets/actions";
import { ASSET_TYPE_LABEL } from "@/app/w/[workspaceId]/assets/labels";
import { AddKnowledgeForm, KnowledgeList } from "@/app/w/[workspaceId]/knowledge/knowledge-list";
import { attempt } from "@/lib/attempt";
import { api, canManage } from "@/lib/relay-api";
import type { AssignmentView, PersonView, TeamView } from "@/lib/types";

import {
  assignOwnerAction,
  endAssignmentAction,
  replacePrimaryAction,
  setResponsibilityStatusAction,
} from "../../actions";
import { ContinuityContext } from "./context";
import {
  AccessSection,
  CorrectAssignment,
  DependenciesSection,
  StewardshipFacts,
} from "./stewardship";

export default async function ResponsibilityPage({
  params,
  searchParams,
}: PageProps<"/w/[workspaceId]/responsibilities/[responsibilityId]">) {
  const [{ workspaceId, responsibilityId }, query] = await Promise.all([params, searchParams]);
  const asOf = typeof query.as_of === "string" ? query.as_of : undefined;
  const [
    workspace,
    detail,
    history,
    people,
    teams,
    assets,
    knowledge,
    context,
    stewardship,
    members,
    responsibilities,
  ] = await Promise.all([
    attempt(api.getWorkspace(workspaceId)),
    attempt(api.getResponsibility(workspaceId, responsibilityId, asOf)),
    attempt(api.responsibilityHistory(workspaceId, responsibilityId)),
    attempt(api.listPeople(workspaceId)),
    attempt(api.listTeams(workspaceId)),
    attempt(api.assets(workspaceId)),
    attempt(api.responsibilityKnowledge(workspaceId, responsibilityId)),
    attempt(api.responsibilityContext(workspaceId, responsibilityId)),
    attempt(api.stewardship(workspaceId, responsibilityId)),
    attempt(api.members(workspaceId)),
    attempt(api.listResponsibilities(workspaceId)),
  ]);
  if (!workspace.ok) return <ApiErrorNotice error={workspace.error} />;
  if (!detail.ok) return <ApiErrorNotice error={detail.error} />;
  if (!history.ok) return <ApiErrorNotice error={history.error} />;
  if (!people.ok) return <ApiErrorNotice error={people.error} />;
  if (!teams.ok) return <ApiErrorNotice error={teams.error} />;

  const r = detail.data;
  const canWriteKnowledge = !["guest", "auditor"].includes(workspace.data.role);
  const linked = new Set(r.assets.map((a) => a.id));
  const linkable = assets.ok ? assets.data.filter((a) => !linked.has(a.id)) : [];
  const manage = canManage(workspace.data) && r.status === "active";
  const base = `/w/${workspaceId}/responsibilities/${responsibilityId}`;

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader
        title={r.name}
        actions={
          <>
            <Link
              href={`${base}/timeline`}
              className={buttonVariants({ variant: "outline", size: "sm" })}
            >
              <History aria-hidden />
              Memory replay
            </Link>
            {canManage(workspace.data) ? (
              <>
                {r.status === "active" ? (
                  <Link
                    href={`${base}/edit`}
                    className={buttonVariants({ variant: "outline", size: "sm" })}
                  >
                    Edit
                  </Link>
                ) : null}
                <ActionForm
                  action={setResponsibilityStatusAction.bind(
                    null,
                    workspaceId,
                    responsibilityId,
                    r.status === "active" ? "archive" : "restore",
                  )}
                >
                  <SubmitButton variant="ghost" size="sm" pendingLabel="…">
                    {r.status === "active" ? "Archive" : "Restore"}
                  </SubmitButton>
                </ActionForm>
              </>
            ) : null}
          </>
        }
      />
      <div className="grid gap-8 p-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="flex min-w-0 flex-col gap-8">
          <div className="flex flex-wrap items-center gap-2">
            <CriticalityBadge value={r.criticality} />
            {r.category ? <Badge tone="muted">{r.category}</Badge> : null}
            {r.status === "archived" ? <Badge tone="warning">Archived</Badge> : null}
          </div>
          {r.description ? (
            <p className="max-w-prose text-sm whitespace-pre-line">{r.description}</p>
          ) : null}
          <StewardshipFacts workspaceId={workspaceId} detail={r} manage={manage} />

          <Section
            title={asOf ? `Owners on ${formatDateTime(r.as_of)}` : "Current owners"}
            aside={
              <form className="flex items-center gap-2" aria-label="View owners at a point in time">
                <DateTimeInput id="as-of" name="as_of" />
                <button
                  type="submit"
                  className={buttonVariants({ variant: "outline", size: "sm" })}
                >
                  View
                </button>
                {asOf ? (
                  <Link href={base} className="text-muted-foreground text-xs hover:underline">
                    Now
                  </Link>
                ) : null}
              </form>
            }
          >
            <OwnerList
              owners={r.owners_as_of}
              extra={
                manage && !asOf
                  ? (o) => (
                      <CorrectAssignment
                        workspaceId={workspaceId}
                        responsibilityId={responsibilityId}
                        assignment={o}
                      />
                    )
                  : undefined
              }
              endAction={
                manage && !asOf
                  ? (id) => endAssignmentAction.bind(null, workspaceId, responsibilityId, id)
                  : undefined
              }
            />
          </Section>

          {context.ok && !asOf ? (
            <ContinuityContext workspaceId={workspaceId} context={context.data} />
          ) : null}
          {stewardship.ok ? (
            <DependenciesSection
              workspaceId={workspaceId}
              responsibilityId={responsibilityId}
              stewardship={stewardship.data}
              manage={manage}
              responsibilities={responsibilities.ok ? responsibilities.data : []}
              assets={assets.ok ? assets.data : []}
            />
          ) : null}
          {stewardship.ok && r.restricted && canManage(workspace.data) ? (
            <AccessSection
              workspaceId={workspaceId}
              responsibilityId={responsibilityId}
              stewardship={stewardship.data}
              members={members.ok ? members.data : []}
            />
          ) : null}

          <section id="knowledge" className="scroll-mt-6">
            <Section
              title="Knowledge"
              description={
                knowledge.ok && knowledge.data.some((k) => k.freshness === "stale")
                  ? "Some items haven't been reviewed in 90 days."
                  : "Procedures, links and context someone new would need."
              }
            >
              {!knowledge.ok ? (
                <ApiErrorNotice error={knowledge.error} />
              ) : knowledge.data.length === 0 ? (
                <p className="rounded-lg border border-dashed p-4 text-sm">
                  <span className="font-medium">Nothing written down yet.</span>{" "}
                  <span className="text-muted-foreground">
                    If the owner left tomorrow, what would their replacement need?
                  </span>
                </p>
              ) : (
                <KnowledgeList
                  workspaceId={workspaceId}
                  items={knowledge.data}
                  canWrite={canWriteKnowledge}
                />
              )}
              {canWriteKnowledge && r.status === "active" ? (
                <AddKnowledgeForm
                  workspaceId={workspaceId}
                  responsibilityId={responsibilityId}
                  canRestrict={canManage(workspace.data)}
                />
              ) : null}
            </Section>
          </section>

          <Section
            title="Assets"
            description="What this responsibility looks after. Ownership stays here, not on the asset."
          >
            {r.assets.length === 0 ? (
              <p className="text-muted-foreground rounded-lg border p-4 text-sm">
                No assets linked yet.
              </p>
            ) : (
              <ul className="divide-y rounded-lg border">
                {r.assets.map((a) => (
                  <li key={a.id} className="flex items-center gap-3 px-4 py-2 text-sm">
                    <Link
                      href={`/w/${workspaceId}/assets/${a.id}`}
                      className="min-w-0 flex-1 truncate font-medium hover:underline"
                    >
                      {a.name}
                    </Link>
                    <Badge tone="muted">{ASSET_TYPE_LABEL[a.asset_type]}</Badge>
                    <span className="text-muted-foreground w-16 text-xs">
                      {a.relationship === "stewards" ? "Stewards" : "Uses"}
                    </span>
                    {manage ? (
                      <ActionForm
                        action={unlinkAssetAction.bind(null, workspaceId, responsibilityId, a.id)}
                      >
                        <SubmitButton variant="ghost" size="sm" pendingLabel="…">
                          Unlink
                        </SubmitButton>
                      </ActionForm>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
            {manage && linkable.length > 0 ? (
              <ActionForm
                action={linkAssetAction.bind(null, workspaceId, responsibilityId)}
                className="flex-row flex-wrap items-center gap-2"
              >
                <select
                  name="asset_id"
                  defaultValue=""
                  aria-label="Asset to link"
                  className={`${inputClass} h-8 max-w-xs`}
                >
                  <option value="" disabled>
                    Link an asset…
                  </option>
                  {linkable.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.name}
                    </option>
                  ))}
                </select>
                <select
                  name="relationship"
                  aria-label="Relationship"
                  className={`${inputClass} h-8 w-28`}
                >
                  <option value="stewards">Stewards</option>
                  <option value="uses">Uses</option>
                </select>
                <SubmitButton variant="outline" size="sm">
                  Link
                </SubmitButton>
              </ActionForm>
            ) : null}
          </Section>

          <Section
            title="Ownership history"
            description="Every assignment and change is kept; nothing is overwritten."
          >
            {history.data.length === 0 ? (
              <p className="text-muted-foreground rounded-lg border p-4 text-sm">
                No ownership changes yet.
              </p>
            ) : (
              <ol className="relative flex flex-col gap-4 border-l pl-5">
                {history.data.map((h) => (
                  <li key={h.id} className="text-sm">
                    <span
                      className="bg-background absolute -left-[5px] mt-1.5 size-2.5 rounded-full border"
                      aria-hidden
                    />
                    <p>
                      <span className="font-medium">{h.assignee.name}</span>{" "}
                      {
                        {
                          assigned: "assigned as",
                          ended: "ended as",
                          extended: "extended as",
                          corrected: "record corrected as",
                        }[h.change_type]
                      }{" "}
                      {ROLE_LABEL[h.role].toLowerCase()}
                    </p>
                    <p className="text-muted-foreground text-xs">
                      {formatDateTime(h.changed_at)} · period {formatDateTime(h.valid_from)} →{" "}
                      {h.valid_to ? formatDateTime(h.valid_to) : "open"}
                    </p>
                    {h.reason ? (
                      <p className="text-muted-foreground mt-0.5 text-xs">“{h.reason}”</p>
                    ) : null}
                  </li>
                ))}
              </ol>
            )}
          </Section>
        </div>

        {manage ? (
          <aside className="flex flex-col gap-6">
            <Section title="Assign an owner">
              <ActionForm
                action={assignOwnerAction.bind(null, workspaceId, responsibilityId)}
                className="rounded-lg border p-4"
              >
                <Field label="Role" htmlFor="role">
                  <select id="role" name="role" defaultValue="backup" className={inputClass}>
                    <option value="primary">Primary owner</option>
                    <option value="co_owner">Co-owner</option>
                    <option value="backup">Backup</option>
                  </select>
                </Field>
                <AssigneeSelect id="assign-to" people={people.data} teams={teams.data} />
                <Field label="Starts (optional, defaults to now)" htmlFor="starts">
                  <DateTimeInput id="starts" name="starts_at" />
                </Field>
                <Field label="Reason (optional)" htmlFor="assign-reason">
                  <input id="assign-reason" name="reason" maxLength={4000} className={inputClass} />
                </Field>
                <SubmitButton size="sm">Assign</SubmitButton>
              </ActionForm>
            </Section>
            <Section
              title="Hand over primary ownership"
              description="Ends the current primary and starts the new one at the same instant."
            >
              <ActionForm
                action={replacePrimaryAction.bind(null, workspaceId, responsibilityId)}
                className="rounded-lg border p-4"
              >
                <AssigneeSelect id="handover-to" people={people.data} teams={teams.data} />
                <Field label="Effective (optional, defaults to now)" htmlFor="effective">
                  <DateTimeInput id="effective" name="effective_at" />
                </Field>
                <Field label="Reason" htmlFor="handover-reason">
                  <input
                    id="handover-reason"
                    name="reason"
                    maxLength={4000}
                    className={inputClass}
                    placeholder="e.g. moved to another team"
                  />
                </Field>
                <SubmitButton size="sm">Hand over</SubmitButton>
              </ActionForm>
            </Section>
          </aside>
        ) : null}
      </div>
    </div>
  );
}

function OwnerList({
  owners,
  endAction,
  extra,
}: {
  owners: AssignmentView[];
  endAction?: (assignmentId: string) => Parameters<typeof ActionForm>[0]["action"];
  extra?: (owner: AssignmentView) => React.ReactNode;
}) {
  if (owners.length === 0) {
    return (
      <p className="rounded-lg border border-dashed p-4 text-sm">
        <span className="font-medium">Nobody owns this.</span>{" "}
        <span className="text-muted-foreground">Assign a primary owner and a backup.</span>
      </p>
    );
  }
  return (
    <ul className="divide-y rounded-lg border">
      {owners.map((o) => (
        <li key={o.id} className="flex items-center gap-3 px-4 py-3 text-sm">
          <RoleBadge value={o.role} />
          <span className="min-w-0 flex-1">
            <span className="font-medium">{o.assignee.name}</span>
            {o.assignee.type === "team" ? (
              <span className="text-muted-foreground ml-1.5 text-xs">Team</span>
            ) : null}
            {o.assignee.status === "archived" ? (
              <Badge tone="warning" className="ml-1.5">
                Archived
              </Badge>
            ) : null}
            <span className="text-muted-foreground block text-xs">
              Since {formatDateTime(o.valid_from)}
              {o.valid_to ? ` · until ${formatDateTime(o.valid_to)}` : ""}
            </span>
            {extra ? extra(o) : null}
          </span>
          {endAction ? (
            <ActionForm action={endAction(o.id)}>
              <SubmitButton
                variant="ghost"
                size="sm"
                pendingLabel="Ending…"
                confirm="End this assignment now? It is kept in the ownership history."
              >
                End
              </SubmitButton>
            </ActionForm>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

function AssigneeSelect({
  id,
  people,
  teams,
}: {
  id: string;
  people: PersonView[];
  teams: TeamView[];
}) {
  return (
    <Field label="Person or team" htmlFor={id}>
      <select id={id} name="assignee" required defaultValue="" className={inputClass}>
        <option value="" disabled>
          {people.length + teams.length === 0 ? "Add people first" : "Choose…"}
        </option>
        {people.length > 0 ? (
          <optgroup label="People">
            {people.map((p) => (
              <option key={p.id} value={`person:${p.id}`}>
                {p.display_name}
              </option>
            ))}
          </optgroup>
        ) : null}
        {teams.length > 0 ? (
          <optgroup label="Teams">
            {teams.map((t) => (
              <option key={t.id} value={`team:${t.id}`}>
                {t.name}
              </option>
            ))}
          </optgroup>
        ) : null}
      </select>
    </Field>
  );
}
