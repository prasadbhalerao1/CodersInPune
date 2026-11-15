import type { Metadata } from "next";
import {
  ArrowRight,
  Bot,
  Check,
  Code2,
  FlaskConical,
  History,
  Lightbulb,
  Sigma,
} from "lucide-react";
import Link from "next/link";

import { RelayMark } from "@/components/brand";
import { EXPLAIN, type Explanation, type ExplainKey } from "@/lib/explain";
import { REPO_URL } from "@/lib/site";

import { DocsNav, type NavGroup } from "./docs-nav";

export const metadata: Metadata = {
  title: "Product guide",
  description:
    "How Relay works: the three headline features, every number and its formula, what AI does and doesn't do, permissions, conflicts and stale data.",
};

const GROUPS: { title: string; intro: string; keys: ExplainKey[] }[] = [
  {
    title: "The three headline features",
    intro: "Each one works on real records and shows the evidence behind what it says.",
    keys: ["copilot", "simulation", "memory_replay"],
  },
  {
    title: "Working with AI, safely",
    intro:
      "Features that do the busywork and stop before anything changes: a person accepts every result.",
    keys: ["autopilot", "ask_relay", "meetings", "decision_log", "continuation_plan"],
  },
  {
    title: "Numbers and how they are calculated",
    intro:
      "Every number in Relay can be traced to the records behind it. The ⓘ next to a number in the app opens the same definition you see here.",
    keys: [
      "readiness",
      "overload",
      "continuity_debt",
      "risk",
      "coverage",
      "key_person",
      "freshness",
      "follow_through",
      "expertise",
    ],
  },
  {
    title: "Trust in what you read",
    intro: "How Relay separates what it knows from what it suggests.",
    keys: ["evidence_labels", "confidence"],
  },
];

const PRINCIPLES = [
  {
    id: "ai",
    title: "What AI does, and what it never does",
    points: [
      "AI drafts: handover briefs, answers to questions, chapters of a project's history, interview questions and coordination messages.",
      "Every AI statement cites the evidence it rests on. A statement citing nothing, or citing something that doesn't exist, is dropped.",
      "AI never changes anything. Models only hold read-only tools; owners, cases and knowledge change only when a person accepts a proposal.",
      "With AI switched off, Relay still works: rule-based briefs, labelled search and every deterministic number stay available.",
    ],
  },
  {
    id: "permissions",
    title: "Permissions",
    points: [
      "Relay shows only what your role allows: owner, admin, continuity manager, knowledge steward, team manager, member, auditor or guest. Unknown roles and permissions are denied.",
      "Restricted and confidential knowledge is limited to managers by a database rule, not just by the interface.",
      "AI receives only the evidence the person asking may see, so a citation never reveals something you couldn't open yourself.",
      "Every workspace is isolated at the database level, and every access decision is written to an append-only audit log.",
    ],
  },
  {
    id: "conflicts",
    title: "When sources disagree",
    points: [
      "A conflict is shown only when two distinct sources say different things, and both are cited side by side.",
      "Relay never picks a winner silently: the person reviewing the brief decides, and the decision is recorded.",
    ],
  },
  {
    id: "stale",
    title: "When data is stale or missing",
    points: [
      "Each connected source shows when it last synced. A failed or partial sync is labelled wherever its data is used.",
      "Knowledge past its review window stays visible with a stale label, so you can judge it yourself.",
      "Briefs list what they could not see, so the reader knows what is missing as well as what is there.",
    ],
  },
];

const FEATURES: { key: ExplainKey; icon: typeof Bot; blurb: string }[] = [
  { key: "copilot", icon: Bot, blurb: "Ask the handover; every answer cites its evidence." },
  {
    key: "simulation",
    icon: FlaskConical,
    blurb: "Rehearse an absence without changing anything.",
  },
  { key: "memory_replay", icon: History, blurb: "Replay how the work got here, from the sources." },
];

export default function DocsPage() {
  const nav: NavGroup[] = [
    ...GROUPS.map((g) => ({
      title: g.title,
      items: g.keys.map((k) => ({ id: k, title: EXPLAIN[k].title })),
    })),
    { title: "Principles", items: PRINCIPLES.map((p) => ({ id: p.id, title: p.title })) },
  ];
  return (
    <div className="bg-background min-h-full">
      <header className="bg-background/80 sticky top-0 z-20 border-b backdrop-blur-md">
        <div className="mx-auto flex h-14 max-w-7xl items-center gap-3 px-4 sm:px-6">
          <Link href="/" className="flex items-center gap-2 font-semibold">
            <RelayMark className="size-6" />
            Relay
          </Link>
          <span className="bg-border h-4 w-px" aria-hidden />
          <span className="text-muted-foreground text-sm">Product guide</span>
          <Link href="/workspaces" className="btn btn-primary btn-sm ml-auto">
            Open Relay
          </Link>
        </div>
      </header>

      <div className="mx-auto grid max-w-7xl gap-12 px-4 sm:px-6 lg:grid-cols-[15rem_minmax(0,1fr)]">
        <aside className="hidden lg:block">
          <div className="sticky top-14 max-h-[calc(100dvh-3.5rem)] overflow-y-auto py-10 pr-2">
            <DocsNav groups={nav} />
          </div>
        </aside>

        <main className="min-w-0 py-10 lg:py-14">
          <p className="text-primary text-[13px] font-medium">Product guide</p>
          <h1 className="font-display mt-2 text-5xl leading-[1.05] tracking-tight sm:text-6xl">
            How Relay works
          </h1>
          <p className="text-muted-foreground mt-5 max-w-2xl text-lg leading-relaxed">
            Relay keeps work moving when people move on. This guide explains every feature and every
            number: what it means, exactly how it is calculated, and the code that does it.
          </p>

          <div className="mt-10 grid gap-3 sm:grid-cols-3">
            {FEATURES.map(({ key, icon: Icon, blurb }) => (
              <a
                key={key}
                href={`#${key}`}
                className="group bg-card hover:border-primary/40 rounded-xl border p-5 shadow-xs transition-[border-color,box-shadow,translate] duration-200 hover:-translate-y-0.5 hover:shadow-md"
              >
                <span className="bg-primary/10 text-primary flex size-9 items-center justify-center rounded-lg">
                  <Icon aria-hidden className="size-[18px]" />
                </span>
                <p className="mt-4 font-semibold">{EXPLAIN[key].title}</p>
                <p className="text-muted-foreground mt-1 text-sm">{blurb}</p>
                <span className="text-primary mt-3 inline-flex items-center gap-1 text-sm font-medium">
                  Read
                  <ArrowRight
                    aria-hidden
                    className="size-3.5 transition-transform group-hover:translate-x-0.5"
                  />
                </span>
              </a>
            ))}
          </div>

          {GROUPS.map((g) => (
            <section key={g.title} aria-labelledby={slug(g.title)} className="mt-20">
              <p
                id={slug(g.title)}
                className="text-muted-foreground text-[11px] font-semibold tracking-[0.08em] uppercase"
              >
                {g.title}
              </p>
              <p className="text-muted-foreground mt-1 max-w-2xl text-sm">{g.intro}</p>
              <div className="divide-y">
                {g.keys.map((k) => (
                  <Entry key={k} id={k} />
                ))}
              </div>
            </section>
          ))}

          <section aria-labelledby="principles" className="mt-20">
            <p
              id="principles"
              className="text-muted-foreground text-[11px] font-semibold tracking-[0.08em] uppercase"
            >
              Principles
            </p>
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              {PRINCIPLES.map((p) => (
                <article
                  key={p.id}
                  id={p.id}
                  className="bg-card scroll-mt-24 rounded-xl border p-5 shadow-xs"
                >
                  <h2 className="font-semibold">{p.title}</h2>
                  <ul className="mt-3 flex flex-col gap-2 text-sm">
                    {p.points.map((point) => (
                      <li key={point} className="flex gap-2">
                        <Check aria-hidden className="text-primary mt-0.5 size-4 shrink-0" />
                        <span className="text-muted-foreground">{point}</span>
                      </li>
                    ))}
                  </ul>
                </article>
              ))}
            </div>
          </section>

          <footer className="text-muted-foreground mt-20 border-t pt-6 text-sm">
            Every formula above links to the code that computes it. The{" "}
            <a href={REPO_URL} className="text-foreground underline underline-offset-2">
              source
            </a>{" "}
            is public.
          </footer>
        </main>
      </div>
    </div>
  );
}

function Entry({ id }: { id: ExplainKey }) {
  const e: Explanation = EXPLAIN[id];
  return (
    <article id={id} className="group/entry scroll-mt-24 py-10">
      <h2 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
        {e.title}
        <a
          href={`#${id}`}
          aria-label={`Link to ${e.title}`}
          className="text-muted-foreground opacity-0 transition-opacity group-hover/entry:opacity-100 focus-visible:opacity-100"
        >
          #
        </a>
      </h2>
      <p className="text-muted-foreground mt-3 max-w-3xl text-[15px] leading-relaxed">
        {e.summary}
      </p>
      {e.formula ? (
        <div className="bg-card mt-6 max-w-3xl overflow-hidden rounded-xl border shadow-xs">
          <p className="bg-muted/50 text-muted-foreground flex items-center gap-2 border-b px-4 py-2 text-xs font-medium">
            <Sigma aria-hidden className="size-3.5" />
            How it is calculated
          </p>
          <p className="px-4 py-3.5 text-[14px] leading-relaxed">{e.formula}</p>
        </div>
      ) : null}
      <div className="mt-6 grid max-w-3xl gap-6 md:grid-cols-2">
        <div>
          <p className="text-xs font-semibold">What it uses</p>
          <ul className="mt-2 flex flex-col gap-1.5 text-sm">
            {e.inputs.map((i) => (
              <li key={i} className="text-muted-foreground flex gap-2">
                <Check aria-hidden className="text-primary mt-0.5 size-4 shrink-0" />
                {i}
              </li>
            ))}
          </ul>
        </div>
        {e.reading ? (
          <div className="border-primary/30 bg-primary/5 rounded-lg border-l-2 px-4 py-3 text-sm">
            <p className="text-primary flex items-center gap-1.5 text-xs font-semibold">
              <Lightbulb aria-hidden className="size-3.5" />
              How to read it
            </p>
            <p className="mt-1">{e.reading}</p>
          </div>
        ) : null}
      </div>
      <a
        href={`${REPO_URL}/blob/main/${e.source.split(" ")[0]}`}
        className="hover:border-foreground/30 text-muted-foreground hover:text-foreground mt-6 inline-flex items-center gap-1.5 rounded-full border px-3 py-1 font-mono text-xs transition-colors"
      >
        <Code2 aria-hidden className="size-3.5" />
        {e.source}
      </a>
    </article>
  );
}

function slug(text: string) {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, "-");
}
