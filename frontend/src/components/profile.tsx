import Link from "next/link";
import type { ReactNode } from "react";

import { EmptyState, formatDateTime, PageHeader, Section } from "@/components/page";
import {
  Badge,
  CaseStatusBadge,
  CriticalityBadge,
  EmergencyBadge,
  RoleBadge,
  SeverityBadge,
} from "@/components/ui/badge";
import type { CaseStatus, CaseType, ProfileRef, ProfileView, Role } from "@/lib/types";

const KIND_LABEL = { person: "Person", team: "Team", department: "Department" } as const;
const CASE_TYPE: Record<CaseType, string> = {
  transfer: "Transfer",
  coverage: "Temporary coverage",
  departure: "Departure",
  onboarding: "Onboarding",
  project_handover: "Project handover",
};

function RefList({
  refs,
  href,
  empty,
}: {
  refs: ProfileRef[];
  href: (id: string) => string;
  empty: string;
}) {
  if (!refs.length) return <p className="text-muted-foreground text-sm">{empty}</p>;
  return (
    <ul className="divide-y rounded-lg border">
      {refs.map((r) => (
        <li key={r.id}>
          <Link
            href={href(r.id)}
            className="hover:bg-muted/40 flex items-center gap-3 px-4 py-2.5 text-sm"
          >
            <span className="min-w-0 flex-1 truncate font-medium">{r.name}</span>
            {r.detail ? <span className="text-muted-foreground text-xs">{r.detail}</span> : null}
          </Link>
        </li>
      ))}
    </ul>
  );
}

function Facts({ items }: { items: [string, ReactNode][] }) {
  const shown = items.filter(([, v]) => v !== null && v !== undefined && v !== "");
  if (!shown.length) return null;
  return (
    <dl className="grid grid-cols-[8rem_1fr] gap-x-4 gap-y-2 rounded-lg border p-4 text-sm">
      {shown.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-muted-foreground">{k}</dt>
          <dd className="min-w-0">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

/** Person, team and department detail: structure and continuity context, never performance. */
export function Profile({ workspaceId, p }: { workspaceId: string; p: ProfileView }) {
  const base = `/w/${workspaceId}`;
  const current = p.roles.filter((r) => r.state === "current");
  const scheduled = p.roles.filter((r) => r.state === "scheduled");
  return (
    <div className="flex flex-1 flex-col">
      <PageHeader
        title={
          <span className="flex items-center gap-2">
            <Link href={`${base}/people`} className="text-muted-foreground hover:text-foreground">
              People &amp; Teams
            </Link>
            <span className="text-muted-foreground">/</span>
            <span className="truncate">{p.name}</span>
          </span>
        }
      />
      <div className="grid gap-8 p-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <div className="flex min-w-0 flex-col gap-8">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="muted">{KIND_LABEL[p.kind]}</Badge>
            {p.status !== "active" ? <Badge tone="warning">Archived</Badge> : null}
            {p.continuity_debt !== null ? (
              <Link
                href={`${base}/insights?department_id=${p.id}`}
                className="text-muted-foreground hover:text-foreground text-sm hover:underline"
              >
                Continuity Debt {p.continuity_debt} →
              </Link>
            ) : null}
          </div>

          <Section
            title="Ownership roles"
            description={
              p.kind === "person"
                ? "Responsibilities this person currently holds or will hold."
                : "Responsibilities held by its people and teams."
            }
          >
            {p.roles.length === 0 ? (
              <EmptyState
                title="No ownership roles"
                description="Assign this as a primary, co-owner, backup or temporary owner from a responsibility's page."
              />
            ) : (
              <div className="overflow-x-auto rounded-lg border">
                <table className="w-full text-sm">
                  <thead className="text-muted-foreground border-b text-left text-xs">
                    <tr>
                      <th className="px-4 py-2 font-medium">Responsibility</th>
                      <th className="px-4 py-2 font-medium">Role</th>
                      {p.kind !== "person" ? (
                        <th className="px-4 py-2 font-medium">Held by</th>
                      ) : null}
                      <th className="px-4 py-2 font-medium">Effective</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {[...current, ...scheduled].map((r) => (
                      <tr key={`${r.responsibility_id}-${r.role}-${r.holder}-${r.valid_from}`}>
                        <td className="px-4 py-2.5">
                          <Link
                            href={`${base}/responsibilities/${r.responsibility_id}`}
                            className="font-medium hover:underline"
                          >
                            {r.responsibility_name}
                          </Link>
                          <span className="ml-2">
                            <CriticalityBadge value={r.criticality} />
                          </span>
                        </td>
                        <td className="px-4 py-2.5">
                          <RoleBadge value={r.role as Role} />
                        </td>
                        {p.kind !== "person" ? (
                          <td className="text-muted-foreground px-4 py-2.5">{r.holder}</td>
                        ) : null}
                        <td className="text-muted-foreground px-4 py-2.5 text-xs whitespace-nowrap">
                          {r.state === "scheduled"
                            ? `Starts ${formatDateTime(r.valid_from)}`
                            : `Since ${formatDateTime(r.valid_from)}`}
                          {r.valid_to ? ` · until ${formatDateTime(r.valid_to)}` : ""}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Section>

          <Section title="Open risks" description="Risk signals on the responsibilities above.">
            {p.risks.length === 0 ? (
              <p className="text-muted-foreground text-sm">No open risks.</p>
            ) : (
              <ul className="divide-y rounded-lg border">
                {p.risks.map((r) => (
                  <li key={r.key}>
                    <Link
                      href={`${base}/risks/${encodeURIComponent(r.key)}`}
                      className="hover:bg-muted/40 flex items-center gap-3 px-4 py-2.5 text-sm"
                    >
                      <SeverityBadge value={r.severity} />
                      <span className="min-w-0 flex-1 truncate">
                        {r.title}
                        {r.subject ? (
                          <span className="text-muted-foreground"> · {r.subject}</span>
                        ) : null}
                      </span>
                      {r.status !== "open" ? (
                        <span className="text-muted-foreground text-xs capitalize">{r.status}</span>
                      ) : null}
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Section>

          {p.cases.length ? (
            <Section title="Active continuity cases">
              <ul className="divide-y rounded-lg border">
                {p.cases.map((c) => (
                  <li key={c.id}>
                    <Link
                      href={`${base}/cases/${c.id}`}
                      className="hover:bg-muted/40 flex flex-wrap items-center gap-3 px-4 py-2.5 text-sm"
                    >
                      <span className="min-w-0 flex-1 truncate font-medium">{c.title}</span>
                      {c.emergency ? <EmergencyBadge /> : null}
                      <span className="text-muted-foreground text-xs">
                        {CASE_TYPE[c.case_type]} · {c.relation}
                      </span>
                      <CaseStatusBadge value={c.status as CaseStatus} />
                    </Link>
                  </li>
                ))}
              </ul>
            </Section>
          ) : null}
        </div>

        <aside className="flex flex-col gap-6">
          <Facts
            items={[
              ["Title", p.title],
              ["Email", p.email],
              [
                "Department",
                p.department ? (
                  <Link href={`${base}/departments/${p.department.id}`} className="hover:underline">
                    {p.department.name}
                  </Link>
                ) : p.kind !== "department" ? (
                  <span className="text-muted-foreground">None</span>
                ) : null,
              ],
              ["About", p.description],
              [
                "Linked accounts",
                p.identities.length
                  ? p.identities.map((i) => `${i.provider}: ${i.handle}`).join(", ")
                  : null,
              ],
            ]}
          />
          {p.kind === "person" ? (
            <Section title="Teams">
              <RefList
                refs={p.teams}
                href={(id) => `${base}/teams/${id}`}
                empty="Not in any team."
              />
            </Section>
          ) : null}
          {p.kind === "team" ? (
            <Section title="Members">
              <RefList
                refs={p.members}
                href={(id) => `${base}/people/${id}`}
                empty="No members yet. Add them from People & Teams."
              />
            </Section>
          ) : null}
          {p.kind === "department" ? (
            <>
              <Section title="Teams">
                <RefList
                  refs={p.teams}
                  href={(id) => `${base}/teams/${id}`}
                  empty="No teams in this department."
                />
              </Section>
              <Section title="People">
                <RefList
                  refs={p.people}
                  href={(id) => `${base}/people/${id}`}
                  empty="No people in this department."
                />
              </Section>
            </>
          ) : null}
        </aside>
      </div>
    </div>
  );
}
