import Link from "next/link";

import { formatDateTime, Section } from "@/components/page";
import { Badge, CaseStatusBadge, EmergencyBadge, SeverityBadge } from "@/components/ui/badge";
import type { ResponsibilityContextView } from "@/lib/types";

const CASE_TYPE = { transfer: "Transfer", coverage: "Temporary coverage", departure: "Departure" };

/** A small, consistent label for where a piece of information comes from. */
export function Provenance({ kind }: { kind: "risk" | "evidence" | "suggestion" }) {
  const label = {
    risk: "Risk signal",
    evidence: "External evidence",
    suggestion: "Suggested, not applied",
  }[kind];
  return (
    <span className="text-muted-foreground rounded border border-dashed px-1.5 py-0.5 text-[10px] font-medium tracking-wide uppercase">
      {label}
    </span>
  );
}

export function ContinuityContext({
  workspaceId,
  context,
}: {
  workspaceId: string;
  context: ResponsibilityContextView;
}) {
  const base = `/w/${workspaceId}`;
  return (
    <>
      <Section
        title="Continuity"
        description="Gaps Relay detected from the catalogue, and continuity cases in progress."
        aside={<Provenance kind="risk" />}
      >
        {context.risks.length === 0 && context.cases.length === 0 ? (
          <p className="text-muted-foreground rounded-lg border px-4 py-3 text-sm">
            No open risks and no active cases.
          </p>
        ) : (
          <ul className="divide-y rounded-lg border">
            {context.risks.map((r) => (
              <li key={r.key}>
                <Link
                  href={`${base}/risks/${encodeURIComponent(r.key)}`}
                  className="hover:bg-muted/40 flex flex-wrap items-center gap-3 px-4 py-2.5 text-sm"
                >
                  <SeverityBadge value={r.severity} />
                  <span className="min-w-0 flex-1">{r.title}</span>
                  {r.status === "accepted" ? (
                    <span className="text-muted-foreground text-xs">
                      Accepted{r.accepted_until ? ` until ${formatDateTime(r.accepted_until)}` : ""}
                    </span>
                  ) : r.status === "acknowledged" ? (
                    <span className="text-muted-foreground text-xs">Acknowledged</span>
                  ) : null}
                </Link>
              </li>
            ))}
            {context.cases.map((c) => (
              <li key={c.id}>
                <Link
                  href={`${base}/cases/${c.id}`}
                  className="hover:bg-muted/40 flex flex-wrap items-center gap-3 px-4 py-2.5 text-sm"
                >
                  <Badge tone="muted">{CASE_TYPE[c.case_type]} case</Badge>
                  <span className="min-w-0 flex-1 truncate font-medium">{c.title}</span>
                  {c.emergency ? <EmergencyBadge /> : null}
                  {!c.recipient_planned ? (
                    <span className="text-xs text-amber-800 dark:text-amber-300">
                      no recipient yet
                    </span>
                  ) : null}
                  <CaseStatusBadge value={c.status} />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Section>

      {context.evidence.length ? (
        <Section
          title="External evidence"
          description="Linked sources and what Relay read from them. Owners are only changed by people."
          aside={<Provenance kind="evidence" />}
        >
          <ul className="divide-y rounded-lg border">
            {context.evidence.map((e) => (
              <li
                key={`${e.source}-${e.url}`}
                className="flex flex-wrap items-center gap-3 px-4 py-2.5 text-sm"
              >
                <Badge tone="muted">{e.source}</Badge>
                <a
                  href={e.url}
                  target="_blank"
                  rel="noreferrer"
                  className="min-w-0 flex-1 truncate font-medium hover:underline"
                >
                  {e.label} ↗
                </a>
                {e.detail ? (
                  <span className="text-muted-foreground text-xs">{e.detail}</span>
                ) : null}
              </li>
            ))}
          </ul>
        </Section>
      ) : null}

      {context.suggestions.length ? (
        <Section
          title="Suggested owners"
          description="Inferred from repository evidence. Nothing changes until someone accepts a suggestion."
          aside={<Provenance kind="suggestion" />}
        >
          <ul className="divide-y rounded-lg border">
            {context.suggestions.map((s) => (
              <li
                key={`${s.label}-${s.reason}`}
                className="flex flex-wrap items-center gap-3 px-4 py-2.5 text-sm"
              >
                <span className="min-w-0 flex-1">
                  <span className="font-medium">{s.label}</span>
                  <span className="text-muted-foreground block text-xs">{s.reason}</span>
                </span>
                <Link
                  href={`${base}/integrations/github/suggestions`}
                  className="text-xs underline-offset-2 hover:underline"
                >
                  Review
                </Link>
              </li>
            ))}
          </ul>
        </Section>
      ) : null}
    </>
  );
}
