import Link from "next/link";

import { EmptyState, Section } from "@/components/page";
import { Badge, CriticalityBadge, ROLE_LABEL } from "@/components/ui/badge";
import type { ImpactView } from "@/lib/types";

const SOURCE_STATE = {
  connected: { label: "Connected", tone: "muted" },
  partial: { label: "Partial: last sync failed or access lost", tone: "warning" },
  not_connected: { label: "Not connected", tone: "muted" },
} as const;

export function ImpactPanel({ workspaceId, impact }: { workspaceId: string; impact: ImpactView }) {
  const unavailable = impact.sources.filter((s) => s.state !== "connected");
  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="text-muted-foreground">Sources</span>
        {impact.sources.map((s) => (
          <Badge key={s.source} tone={SOURCE_STATE[s.state].tone}>
            {s.source}: {SOURCE_STATE[s.state].label}
          </Badge>
        ))}
      </div>
      {unavailable.some((s) => s.state === "partial") ? (
        <p className="rounded-lg border border-amber-600/30 bg-amber-50 p-3 text-sm text-amber-950 dark:bg-amber-950/30 dark:text-amber-100">
          Some connected tools could not be read fully. Pull requests, issues or pages from them may
          be missing below; absence here does not mean there is no work.
        </p>
      ) : null}
      {impact.items.length === 0 ? (
        <EmptyState
          title="Nothing in scope yet"
          description="Add responsibilities to the case to see the assets, open work and knowledge they carry."
        />
      ) : (
        impact.items.map((item) => (
          <Section
            key={item.scope_item_id}
            title={
              <span className="flex flex-wrap items-center gap-2">
                <Link
                  href={`/w/${workspaceId}/responsibilities/${item.responsibility_id}`}
                  className="underline-offset-2 hover:underline"
                >
                  {item.responsibility_name}
                </Link>
                <CriticalityBadge value={item.criticality} />
                <Badge tone="muted">{ROLE_LABEL[item.role]}</Badge>
              </span>
            }
            description={`${item.current_owner_name ?? "No current holder"} → ${
              item.recipient_name ?? "recipient not chosen"
            }${item.state === "applied" ? " · handed over" : ""}`}
          >
            <div className="grid gap-4 md:grid-cols-2">
              <div className="rounded-lg border p-3 text-sm">
                <p className="text-muted-foreground mb-2 text-xs font-medium">Assets stewarded</p>
                {item.assets.length ? (
                  <ul className="flex flex-col gap-1">
                    {item.assets.map((a) => (
                      <li key={a.id} className="flex items-center gap-2">
                        <Link
                          href={`/w/${workspaceId}/assets/${a.id}`}
                          className="underline-offset-2 hover:underline"
                        >
                          {a.name}
                        </Link>
                        <span className="text-muted-foreground text-xs">
                          {a.asset_type.replaceAll("_", " ")}
                          {a.status !== "active" ? ` · ${a.status}` : ""}
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-muted-foreground">No assets linked.</p>
                )}
              </div>
              <div className="rounded-lg border p-3 text-sm">
                <p className="text-muted-foreground mb-2 text-xs font-medium">Knowledge</p>
                <p>
                  {item.knowledge.total
                    ? `${item.knowledge.total} item${item.knowledge.total === 1 ? "" : "s"}`
                    : "Nothing written down"}
                  {item.knowledge.stale ? (
                    <Badge tone="warning" className="ml-2">
                      {item.knowledge.stale} overdue for review
                    </Badge>
                  ) : null}
                </p>
              </div>
              <div className="rounded-lg border p-3 text-sm md:col-span-2">
                <p className="text-muted-foreground mb-2 text-xs font-medium">
                  Connected work and documents
                </p>
                {item.evidence.length ? (
                  <ul className="flex flex-col gap-1.5">
                    {item.evidence.map((e) => (
                      <li
                        key={`${e.source}:${e.url}`}
                        className="flex flex-wrap items-baseline gap-2"
                      >
                        <Badge tone="muted">{e.source}</Badge>
                        <a
                          href={e.url}
                          target="_blank"
                          rel="noreferrer"
                          className="underline-offset-2 hover:underline"
                        >
                          {e.label}
                        </a>
                        {e.detail ? (
                          <span className="text-muted-foreground text-xs">{e.detail}</span>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-muted-foreground">
                    No GitHub repositories, Linear projects or Notion sources are linked to this
                    responsibility.
                  </p>
                )}
              </div>
              {item.risks.length ? (
                <div className="rounded-lg border p-3 text-sm md:col-span-2">
                  <p className="text-muted-foreground mb-2 text-xs font-medium">Open risks</p>
                  <ul className="flex flex-col gap-1">
                    {item.risks.map((r) => (
                      <li key={r.key} className="flex items-center gap-2">
                        <Badge tone={r.severity === "high" ? "danger" : "warning"}>
                          {r.severity}
                        </Badge>
                        {r.title}
                        <span className="text-muted-foreground text-xs">{r.status}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
          </Section>
        ))
      )}
    </div>
  );
}
