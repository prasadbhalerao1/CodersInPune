import type { Metadata } from "next";
import Link from "next/link";

import { inputClass } from "@/components/action-form";
import { ApiErrorNotice } from "@/components/api-error-notice";
import { EmptyState, formatDateTime, PageHeader, Section } from "@/components/page";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { attempt } from "@/lib/attempt";
import { api } from "@/lib/relay-api";
import { hitPath, KIND_GROUP } from "@/lib/search";
import type { SearchKind } from "@/lib/types";
import { cn } from "@/lib/utils";

export const metadata: Metadata = { title: "Search" };

const STALE_DAYS = 30;
const isKind = (v: unknown): v is SearchKind => typeof v === "string" && v in KIND_GROUP;

export default async function SearchPage({
  params,
  searchParams,
}: PageProps<"/w/[workspaceId]/search">) {
  const [{ workspaceId }, query] = await Promise.all([params, searchParams]);
  const q = typeof query.q === "string" ? query.q.trim() : "";
  const kind = isKind(query.kind) ? query.kind : undefined;
  const base = `/w/${workspaceId}`;
  const [results, experts] =
    q.length >= 2
      ? await Promise.all([
          attempt(api.searchFull(workspaceId, q, kind)),
          attempt(api.experts(workspaceId, q)),
        ])
      : [null, null];
  if (results && !results.ok) return <ApiErrorNotice error={results.error} />;
  const now = new Date().getTime(); // server component: rendered per request
  const facets = results?.ok ? results.data.facets : {};
  const total = Object.values(facets).reduce((a, b) => a + (b ?? 0), 0);
  const link = (k?: SearchKind) =>
    `${base}/search?q=${encodeURIComponent(q)}${k ? `&kind=${k}` : ""}`;

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader title="Search" />
      <div className="grid gap-8 p-6 xl:grid-cols-[minmax(0,1fr)_20rem]">
        <div className="flex min-w-0 flex-col gap-5">
          <form method="get" action={`${base}/search`} role="search" className="flex gap-2">
            <input
              name="q"
              defaultValue={q}
              autoFocus
              placeholder="Search responsibilities, people, knowledge, cases, GitHub and Linear…"
              aria-label="Search"
              className={inputClass}
            />
            <Button type="submit" variant="outline">
              Search
            </Button>
          </form>
          {q.length < 2 ? (
            <EmptyState
              title="Search everything you can see"
              description="Results respect your access: restricted responsibilities, managers-only knowledge and disconnected sources never appear."
            />
          ) : results?.ok ? (
            <>
              <nav aria-label="Result types" className="flex flex-wrap gap-1 text-sm">
                <Link
                  href={link()}
                  aria-current={!kind ? "page" : undefined}
                  className={cn(
                    "rounded-md px-2.5 py-1",
                    !kind
                      ? "bg-foreground/[0.06] font-medium"
                      : "text-muted-foreground hover:bg-muted",
                  )}
                >
                  All <span className="text-muted-foreground tabular-nums">{total}</span>
                </Link>
                {(Object.keys(facets) as SearchKind[]).map((k) => (
                  <Link
                    key={k}
                    href={link(k)}
                    aria-current={kind === k ? "page" : undefined}
                    className={cn(
                      "rounded-md px-2.5 py-1",
                      kind === k
                        ? "bg-foreground/[0.06] font-medium"
                        : "text-muted-foreground hover:bg-muted",
                    )}
                  >
                    {KIND_GROUP[k]}{" "}
                    <span className="text-muted-foreground tabular-nums">{facets[k]}</span>
                  </Link>
                ))}
              </nav>
              {results.data.hits.length === 0 ? (
                <EmptyState
                  title="No results"
                  description="Try other words, or check the spelling."
                />
              ) : (
                <ul className="divide-y rounded-lg border">
                  {results.data.hits.map((h) => {
                    const stale =
                      h.updated_at !== null &&
                      now - new Date(h.updated_at).getTime() > STALE_DAYS * 86_400_000;
                    const body = (
                      <>
                        <span className="min-w-0 flex-1">
                          <span className="block truncate font-medium">{h.title}</span>
                          <span className="text-muted-foreground block truncate text-xs">
                            {[h.detail, h.status && h.status !== "active" ? h.status : null]
                              .filter(Boolean)
                              .join(" · ")}
                          </span>
                        </span>
                        <Badge tone="muted">{KIND_GROUP[h.kind]}</Badge>
                        {h.updated_at ? (
                          <span
                            className={cn(
                              "text-xs",
                              stale
                                ? "text-amber-700 dark:text-amber-300"
                                : "text-muted-foreground",
                            )}
                          >
                            {stale ? "Not updated since " : "Updated "}
                            {formatDateTime(h.updated_at)}
                          </span>
                        ) : null}
                      </>
                    );
                    return (
                      <li key={`${h.kind}:${h.id}:${h.title}`}>
                        {h.url ? (
                          <a
                            href={h.url}
                            target="_blank"
                            rel="noreferrer"
                            className="hover:bg-muted/40 flex items-center gap-3 px-4 py-2.5 text-sm"
                          >
                            {body}
                          </a>
                        ) : (
                          <Link
                            href={`${base}${hitPath(h)}`}
                            className="hover:bg-muted/40 flex items-center gap-3 px-4 py-2.5 text-sm"
                          >
                            {body}
                          </Link>
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
            </>
          ) : null}
        </div>
        {q.length >= 2 ? (
          <aside>
            <Section
              title="Who to ask"
              description="People connected to this topic, with the evidence. Not a ranking."
            >
              {experts?.ok && experts.data.length ? (
                <ul className="flex flex-col gap-3 text-sm">
                  {experts.data.map((e) => (
                    <li key={e.person_id}>
                      <Link
                        href={`${base}/people/${e.person_id}`}
                        className="font-medium hover:underline"
                      >
                        {e.name}
                      </Link>
                      <ul className="text-muted-foreground mt-0.5 flex flex-col gap-0.5 text-xs">
                        {e.reasons.map((r, i) => (
                          <li key={i}>{r.text}</li>
                        ))}
                      </ul>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-muted-foreground text-sm">
                  Nobody is connected to this topic in what you can see.
                </p>
              )}
            </Section>
          </aside>
        ) : null}
      </div>
    </div>
  );
}
