import Link from "next/link";

import { ApiErrorNotice } from "@/components/api-error-notice";
import { PageHeader, Section } from "@/components/page";
import { CriticalityBadge, SeverityBadge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { attempt } from "@/lib/attempt";
import { api } from "@/lib/relay-api";

export default async function RiskPage({ params }: PageProps<"/w/[workspaceId]/risks/[riskKey]">) {
  const { workspaceId, riskKey } = await params;
  const risks = await attempt(api.risks(workspaceId));
  if (!risks.ok) return <ApiErrorNotice error={risks.error} />;
  const key = decodeURIComponent(riskKey);
  const risk = risks.data.find((r) => r.key === key);
  const base = `/w/${workspaceId}`;

  if (!risk) {
    return (
      <div className="flex flex-1 flex-col">
        <PageHeader title="Risk resolved" />
        <div className="flex flex-col items-start gap-3 p-6 text-sm">
          <p>This risk is no longer open. The catalogue change that caused it has been fixed.</p>
          <Link
            href={`${base}/risks`}
            className={buttonVariants({ variant: "outline", size: "sm" })}
          >
            Back to risks
          </Link>
        </div>
      </div>
    );
  }

  const subjects = risk.responsibility ? [risk.responsibility] : risk.related;
  return (
    <div className="flex flex-1 flex-col">
      <PageHeader title={risk.title} actions={<SeverityBadge value={risk.severity} />} />
      <div className="flex max-w-2xl flex-col gap-6 p-6">
        <Section title="Why this is a risk">
          <p className="text-sm">{risk.explanation}</p>
        </Section>
        <Section title="Recommended action">
          <p className="text-sm">{risk.recommendation}</p>
        </Section>
        <Section
          title={subjects.length > 1 ? "Affected responsibilities" : "Affected responsibility"}
        >
          <ul className="divide-y rounded-lg border">
            {subjects.map((s) => (
              <li key={s.id}>
                <Link
                  href={`${base}/responsibilities/${s.id}`}
                  className="hover:bg-muted/40 flex items-center justify-between gap-3 px-4 py-3 text-sm"
                >
                  <span className="font-medium">{s.name}</span>
                  <CriticalityBadge value={s.criticality} />
                </Link>
              </li>
            ))}
          </ul>
        </Section>
        <p className="text-muted-foreground text-xs">Rule: {risk.rule}</p>
      </div>
    </div>
  );
}
