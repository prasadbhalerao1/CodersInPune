import type { Metadata } from "next";
import Link from "next/link";

import { ApiErrorNotice } from "@/components/api-error-notice";
import { Checklist, GuidanceSwitch, IntegrationStatus, TourList } from "@/components/guidance";
import { PageHeader, Section } from "@/components/page";
import { attempt } from "@/lib/attempt";
import { api } from "@/lib/relay-api";

export const metadata: Metadata = { title: "Learn Relay" };

const START = [
  {
    title: "Someone is leaving or moving",
    text: "Open a departure or transfer case. Relay lists what they own, drafts tasks and readiness checks, and builds a handover the recipient acknowledges.",
    path: "/cases/new?type=departure",
    cta: "Start a departure",
  },
  {
    title: "Someone is away for a while",
    text: "Open a coverage case with an end date. Backups take over for the period and ownership returns automatically.",
    path: "/cases/new?type=coverage",
    cta: "Plan cover",
  },
  {
    title: "Find the gaps before they hurt",
    text: "Risks lists responsibilities with no owner, no backup or an overdue review. Assign one or open a case straight from it.",
    path: "/risks",
    cta: "Review risks",
  },
  {
    title: "Write down how things are done",
    text: "Add procedures and decisions to a responsibility. A steward verifies them; stale or disputed knowledge is flagged.",
    path: "/knowledge",
    cta: "Open knowledge",
  },
];

const TERMS: [string, string][] = [
  [
    "Responsibility",
    "Something that must keep working, with a primary owner, backups and a review cadence.",
  ],
  [
    "Case",
    "A tracked change of who does what: transfer, coverage, departure, onboarding or project handover.",
  ],
  ["Readiness", "Checks that must be met (or waived with a reason) before a case can complete."],
  ["Evidence", "A cited record from Relay, GitHub, Linear or Notion that a finding is based on."],
  [
    "Fact · Rule · AI inference",
    "How a finding was reached. Only facts come straight from a source.",
  ],
  [
    "Capsule",
    "The handover for one recipient: versioned, approved by a second person, acknowledged.",
  ],
  ["Proposal", "A suggested change from rules or AI. Nothing happens until a person accepts it."],
];

const KEYS: [string, string][] = [
  ["Ctrl/⌘ K", "Search and jump anywhere"],
  ["Tab / Shift Tab", "Move between controls"],
  ["Enter", "Submit the focused form"],
  ["Esc", "Close a menu or dialog"],
];

export default async function HelpPage({ params }: PageProps<"/w/[workspaceId]/help">) {
  const { workspaceId } = await params;
  const base = `/w/${workspaceId}`;
  const feedback = process.env.RELAY_FEEDBACK_EMAIL;
  const guidance = await attempt(api.guidance(workspaceId));

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader
        title="Learn Relay"
        description="Short guided tours, your setup checklist and help. Tours unlock as your workspace has the data they show."
      />
      <div className="flex max-w-4xl flex-col gap-8 p-6">
        {guidance.ok ? (
          <>
            <div id="learn" className="flex scroll-mt-20 flex-col gap-8">
              <GuidanceSwitch workspaceId={workspaceId} enabled={guidance.data.enabled} />
              <Section
                title="Tutorials"
                description="Start, resume or replay any tour. Close one at any step and it resumes where you left off."
              >
                <TourList workspaceId={workspaceId} tours={guidance.data.tours} />
              </Section>
            </div>
            <Section
              title="Setup checklist"
              description="What makes continuity work here. Connecting tools is optional: Relay is useful without them."
            >
              <Checklist items={guidance.data.checklist} />
            </Section>
            <Section
              title="Connected tools"
              description="A tool counts as ready only once its first sync has finished and no sync is still queued or retrying."
            >
              <IntegrationStatus guidance={guidance.data} />
            </Section>
          </>
        ) : (
          <ApiErrorNotice error={guidance.error} />
        )}
        <Section title="Get started" description="The four things most teams do first.">
          <div className="grid gap-3 sm:grid-cols-2">
            {START.map((s) => (
              <Link
                key={s.title}
                href={base + s.path}
                className="group hover:border-foreground/25 flex flex-col gap-1 rounded-lg border p-4 transition-colors"
              >
                <span className="text-sm font-medium">{s.title}</span>
                <span className="text-muted-foreground text-sm">{s.text}</span>
                <span className="mt-1 text-sm font-medium group-hover:underline">{s.cta} →</span>
              </Link>
            ))}
          </div>
        </Section>

        <Section title="Words Relay uses">
          <dl className="divide-y rounded-lg border text-sm">
            {TERMS.map(([term, meaning]) => (
              <div key={term} className="grid gap-1 px-4 py-3 sm:grid-cols-[13rem_1fr]">
                <dt className="font-medium">{term}</dt>
                <dd className="text-muted-foreground">{meaning}</dd>
              </div>
            ))}
          </dl>
        </Section>

        <div className="grid gap-8 sm:grid-cols-2">
          <Section title="Keyboard">
            <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
              {KEYS.map(([key, action]) => (
                <div key={key} className="contents">
                  <dt>
                    <kbd className="bg-muted rounded border px-1.5 py-0.5 font-mono text-xs">
                      {key}
                    </kbd>
                  </dt>
                  <dd className="text-muted-foreground">{action}</dd>
                </div>
              ))}
            </dl>
          </Section>
          <Section title="Who can do what">
            <p className="text-muted-foreground text-sm">
              Each role and its permissions are listed in{" "}
              <Link href={`${base}/settings`} className="text-foreground underline">
                Settings
              </Link>
              . If something is unavailable, Relay tells you which role is needed.{" "}
              <Link href={`${base}/settings/data`} className="text-foreground underline">
                Data &amp; privacy
              </Link>{" "}
              explains what Relay reads and why.
            </p>
          </Section>
        </div>

        <Section title="Feedback">
          {feedback ? (
            <p className="text-sm">
              Something confusing, missing or broken?{" "}
              <a
                href={`mailto:${feedback}?subject=${encodeURIComponent("Relay feedback")}`}
                className="font-medium underline"
              >
                Email the team
              </a>
              . Include what you expected and, for errors, the reference shown on the error page.
            </p>
          ) : (
            <p className="text-muted-foreground text-sm">
              Tell your workspace admin. Error pages show a reference they can look up.
            </p>
          )}
        </Section>
      </div>
    </div>
  );
}
