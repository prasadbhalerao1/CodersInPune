import Link from "next/link";

import { ApiErrorNotice } from "@/components/api-error-notice";
import { EmptyState, PageHeader } from "@/components/page";
import { SeverityBadge } from "@/components/ui/badge";
import { attempt } from "@/lib/attempt";
import { api } from "@/lib/relay-api";

import { GitHubTabs } from "../tabs";

export default async function SignalsPage({
  params,
}: PageProps<"/w/[workspaceId]/integrations/github/signals">) {
  const { workspaceId } = await params;
  const signals = await attempt(api.githubSignals(workspaceId));
  if (!signals.ok) return <ApiErrorNotice error={signals.error} />;

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader title="GitHub" />
      <GitHubTabs workspaceId={workspaceId} current="signals" />
      <div className="flex max-w-5xl flex-col gap-4 p-6">
        <p className="text-muted-foreground max-w-prose text-sm">
          Where declared ownership and recent GitHub activity disagree. Each signal links to its
          evidence. Signals never change ownership; act on them through the responsibility or a
          transfer case.
        </p>
        {signals.data.length === 0 ? (
          <EmptyState
            title="No signals"
            description="Declared owners match recent activity, and every active repository is looked after."
          />
        ) : (
          <ul className="divide-y rounded-lg border">
            {signals.data.map((s) => (
              <li key={s.key} className="flex items-start gap-3 px-4 py-3 text-sm">
                <SeverityBadge value={s.severity} />
                <div className="min-w-0 flex-1">
                  <p>
                    <span className="font-medium">{s.title}</span>
                    <span className="text-muted-foreground mx-1.5">·</span>
                    <a
                      href={s.repository_url}
                      target="_blank"
                      rel="noreferrer"
                      className="hover:underline"
                    >
                      {s.repository}
                    </a>
                    {s.responsibility ? (
                      <>
                        <span className="text-muted-foreground mx-1.5">·</span>
                        <Link
                          href={`/w/${workspaceId}/responsibilities/${s.responsibility.id}`}
                          className="hover:underline"
                        >
                          {s.responsibility.name}
                        </Link>
                      </>
                    ) : null}
                  </p>
                  <p className="text-muted-foreground">{s.explanation}</p>
                  {s.evidence.length ? (
                    <ul className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-xs">
                      {s.evidence.map((e) => (
                        <li key={e.url}>
                          <a
                            href={e.url}
                            target="_blank"
                            rel="noreferrer"
                            className="text-muted-foreground hover:text-foreground underline-offset-2 hover:underline"
                          >
                            {e.label} ↗
                          </a>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
