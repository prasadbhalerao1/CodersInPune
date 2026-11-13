import Link from "next/link";
import {
  ArrowRight,
  ArrowUpRight,
  Clock,
  Database,
  FileCheck,
  KeyRound,
  ScrollText,
  ShieldCheck,
} from "lucide-react";

import { RelayMark } from "@/components/brand";
import { HeroSandbox } from "@/components/landing/hero-sandbox";
import { Chip, Feature, body, panel } from "@/components/landing/landing-parts";
import { MemoryReplayPreview } from "@/components/landing/memory-replay-preview";
import { Petals } from "@/components/landing/petals";
import { SectionHeading } from "@/components/landing/section";
import { Walkthrough } from "@/components/landing/walkthrough";
import { REPO_URL } from "@/lib/site";

const SOURCES = [
  {
    name: "GitHub",
    how: "Installed as a read-only GitHub App",
    reads: [
      "Repositories, teams, CODEOWNERS, catalog descriptors",
      "Pull request and issue metadata",
      "Signed webhooks plus a six-hourly reconciliation",
    ],
    never: "Never reads source code, commit diffs or discussion bodies.",
  },
  {
    name: "Linear",
    how: "OAuth 2.0, tokens encrypted at rest",
    reads: [
      "Teams, projects, active cycles, high and urgent issues",
      "Matches contributors to your directory over a rolling 90 days",
      "Flags when a declared owner is not the active assignee",
    ],
    never: "Private projects start managers-only; widening is an audited decision.",
  },
  {
    name: "Notion",
    how: "OAuth, fail-closed by design",
    reads: [
      "Discovers page hierarchies",
      "Imports only pages an admin maps to a responsibility",
      "Tracks edit time and a text revision hash per page",
    ],
    never: "Unmapped pages are never imported. Disconnect withdraws the evidence.",
  },
];

const PRINCIPLES = [
  {
    num: "01",
    title: "Rules decide",
    tone: "var(--ac)",
    points: [
      "Risks, readiness, simulation and overload are deterministic rules you can read on the page.",
      "Missing owners, stale knowledge and conflicting runbooks are found before any model runs.",
    ],
  },
  {
    num: "02",
    title: "AI explains",
    tone: "var(--peri)",
    points: [
      "Every AI statement cites evidence Relay validates, or it is dropped. A conflict needs two sources.",
      "Models hold read-only tools. They cannot change ownership, approve, acknowledge or edit a source.",
    ],
  },
  {
    num: "03",
    title: "People approve",
    tone: "var(--ac)",
    points: [
      "Proposals wait for a human; accepting one goes through the normal services and the audit log.",
      "Any edit to a brief is a new version that needs approval again.",
    ],
  },
];

const EVAL = [
  { value: "31", label: "labelled AI evaluation cases", sub: "12 categories, run in CI" },
  { value: "0", label: "unsupported claims stored", sub: "of 6 attempted, all blocked" },
  { value: "0", label: "permission leaks", sub: "restricted sources never reach the model" },
  { value: "100%", label: "conflict detection", sub: "0 false positives, scripted run" },
];

const SPEC = [
  {
    icon: Database,
    code: "PostgreSQL // forced RLS",
    title: "Tenant isolation lives in the database",
    desc: "Row Level Security is forced on every tenant table and the application connects as a role with no superuser and no BYPASSRLS. A bug in application code cannot read another tenant. Tests inspect the schema to keep it that way.",
    spec: "Every tenant table",
  },
  {
    icon: Clock,
    code: "Temporal GiST constraints",
    title: "Double ownership cannot be written",
    desc: "Exclusion constraints reject overlapping primary-ownership windows. History is valid-time tracked, so the past stays queryable and the present stays unambiguous.",
    spec: "No overlapping owners",
  },
  {
    icon: ScrollText,
    code: "Append-only audit",
    title: "Every change leaves a receipt",
    desc: "Audit events commit in the same transaction as the change and the table is append-only: the app role cannot delete them, and metadata holds identifiers, never secrets or content.",
    spec: "Same-transaction audit",
  },
  {
    icon: ShieldCheck,
    code: "Permissions before retrieval",
    title: "Evidence you may not see never reaches the AI",
    desc: "Each source carries an audience. Restricted evidence is removed before any model sees it for that viewer, and the omissions are counted on the page, not silently hidden.",
    spec: "Audience per source",
  },
  {
    icon: FileCheck,
    code: "Grounded citation gate",
    title: "If it can't be cited, it isn't said",
    desc: "The Copilot answers only from the brief's authorised evidence and says Not in the evidence otherwise. With AI switched off, Relay falls back to labelled search and rule-based briefs.",
    spec: "Cited or dropped",
  },
  {
    icon: KeyRound,
    code: "Secrets and lifecycle",
    title: "Encrypted, exportable, deletable",
    desc: "Integration tokens are encrypted with a dedicated key and never logged. Workspaces export on demand, deletion has a 30-day grace period, and connector data is purged 30 days after disconnect.",
    spec: "You keep control",
  },
];

const PROOF = [
  { value: "250+", label: "backend tests", sub: "real PostgreSQL, as the restricted app role" },
  { value: "31", label: "AI evaluation cases", sub: "enforced in CI, no paid calls" },
  { value: "≤383ms", label: "p95 read latency", sub: "at 1,000 responsibilities" },
  { value: "15", label: "domain modules", sub: "one API, one worker, one database" },
];

const TRY = [
  [
    "Create the sample workspace",
    "One click gives you Northwind Labs: eight people, seven responsibilities, a year of GitHub, Linear and Notion history, and Arjun, who is leaving.",
  ],
  [
    "Replay a project",
    "Open Production deployments, press Replay history, then ask why every payments-api deploy needs a canary. The answer cites events.",
  ],
  [
    "Ask what if",
    "Open Arjun and choose What if he is unavailable. See what breaks, who could cover, and who is already overloaded.",
  ],
  [
    "Plan a real handover",
    "Turn the simulation into a case, generate the brief, approve a version, and watch the recipient acknowledge it.",
  ],
  [
    "Check it took hold",
    "After execution, Follow-through shows per responsibility whether the new holder is settled, settling in, or needs a check-in.",
  ],
];

function Orb({ className }: { className: string }) {
  return <div aria-hidden className={`orb absolute hidden rounded-full md:block ${className}`} />;
}

/** What the crystal refracts: orchid petals and glossy orbs, spread down the whole page. */
export function BlueArt() {
  const cluster = (flip: boolean) => [
    { x: flip ? 560 : 640, y: 780, rot: flip ? 30 : -30, s: 1.2, o: 0.95 },
    { x: flip ? 420 : 780, y: 800, rot: flip ? 70 : -72, s: 1.0, o: 0.75, blur: true },
    { x: flip ? 700 : 520, y: 790, rot: flip ? -8 : 10, s: 1.35, o: 0.9 },
  ];
  const sizes = "pointer-events-none absolute h-[780px] w-[78vw] max-w-[1200px]";
  // Positions are percentages of the whole page so the art spans hero to footer.
  const clusters: Array<[string, boolean]> = [
    ["top-[0.2%] -right-[18%]", false],
    ["top-[9%] -left-[18%]", true],
    ["top-[17%] -right-[16%]", false],
    ["top-[26%] -left-[16%]", true],
    ["top-[35%] -right-[14%]", false],
    ["top-[44%] -left-[16%]", true],
    ["top-[53%] -right-[14%]", false],
    ["top-[62%] -left-[14%]", true],
    ["top-[71%] -right-[14%]", false],
  ];
  const orbs = [
    "top-[7%] -left-16 h-44 w-44",
    "top-[15%] -right-8 h-28 w-28",
    "top-[24%] -left-24 h-56 w-56",
    "top-[33%] -right-6 h-32 w-32",
    "top-[42%] -left-14 h-40 w-40",
    "top-[51%] -right-16 h-52 w-52",
    "top-[60%] -left-8 h-28 w-28",
    "top-[69%] -right-10 h-40 w-40",
  ];
  return (
    <div aria-hidden className="layer pointer-events-none absolute inset-0 z-0 overflow-clip">
      {clusters.map(([pos, flip]) => (
        <Petals key={pos} className={`${sizes} ${pos} opacity-75`} petals={cluster(flip)} />
      ))}
      {orbs.map((o) => (
        <Orb key={o} className={o} />
      ))}
    </div>
  );
}

/** The second half of the page: cobalt and periwinkle (plus lime in dark mode), in serif. */
export function BlueHalf() {
  return (
    <>
      {/* SIMULATOR */}
      <section
        id="simulator"
        className="relative snap-start snap-always scroll-mt-12 overflow-clip py-20 md:mt-14 md:py-24"
      >
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 max-lg:hidden"
          style={{
            clipPath: "polygon(52% 0%, 100% 0%, 100% 100%, 30% 100%)",
            background: "linear-gradient(160deg, #1A2C9E 0%, #2540C8 50%, #3B5BFF 100%)",
            opacity: 0.5,
            maskImage: "linear-gradient(to bottom, transparent, #000 14%, #000 86%, transparent)",
            WebkitMaskImage:
              "linear-gradient(to bottom, transparent, #000 14%, #000 86%, transparent)",
          }}
        />
        <div
          aria-hidden
          className="pointer-events-none absolute top-1/2 right-[8%] hidden h-[520px] w-[640px] -translate-y-1/2 bg-[radial-gradient(ellipse_at_center,var(--bloom),transparent_65%)] blur-3xl lg:block"
        />
        <div className="relative mx-auto grid max-w-7xl items-start gap-14 px-6 sm:px-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,34rem)] lg:px-12">
          <div className="lg:sticky lg:top-28 lg:self-start">
            <SectionHeading
              theme="blue"
              align="left"
              compact
              eyebrow="Try the forecast"
              title="Don't wait for the"
              accent="resignation."
              description="This is the What If? simulator in miniature. Pick an absence window, hand the work to a candidate, and watch readiness move. In the product it is deterministic and read-only: it never touches a real ownership record."
            />
            <ol className="mt-10 space-y-5">
              {[
                ["01", "Choose how long they're gone"],
                ["02", "See what has no backup"],
                ["03", "Try a successor, check their load"],
              ].map(([n, t]) => (
                <li key={n} className="reveal flex items-baseline gap-5">
                  <span className="font-bebas display-outline text-4xl leading-none tracking-wider">
                    {n}
                  </span>
                  <span className="text-fg-soft text-lg">{t}</span>
                </li>
              ))}
            </ol>
          </div>
          <div className="reveal relative">
            <HeroSandbox />
          </div>
        </div>
      </section>

      <div className="relative">
        <div className="relative z-10">
          {/* FEATURES */}
          <section
            id="product"
            className="relative snap-start snap-always scroll-mt-12 py-20 md:mt-14 md:py-24"
          >
            <div className="relative mx-auto max-w-7xl px-6 sm:px-8 lg:px-12">
              <div className="flex flex-col justify-between gap-6 md:flex-row md:items-end">
                <SectionHeading
                  theme="blue"
                  align="left"
                  eyebrow="The product"
                  title="Everything a handover"
                  accent="actually needs."
                />
                <p className="reveal scrim text-fg-mute max-w-sm text-sm leading-relaxed">
                  Eight capabilities, built to hand off to each other. The people and numbers on
                  these cards are the synthetic Northwind Labs sample.
                </p>
              </div>

              <div className="mt-12 grid gap-5 md:mt-14 lg:grid-cols-3">
                {/* Accountability map */}
                <Feature
                  kicker="Accountability map"
                  tone="var(--ac)"
                  title="Ownership for"
                  accent="any work"
                >
                  <p className={body}>
                    Not just services. Vendor renewals, compliance exports and on-call knowledge get
                    a primary owner, co-owners and backups, for people and for teams, with full
                    ownership history and a review cadence of 7 to 730 days.
                  </p>
                  <ul className={`${panel} space-y-3 text-xs`}>
                    {[
                      ["Production deployments", "Arjun · primary", "Leo · backup", "var(--ac)"],
                      ["Vendor contract renewal", "Priya · primary", "No backup", "var(--coral)"],
                      [
                        "Quarterly compliance export",
                        "Mira · primary",
                        "Review due",
                        "var(--peri)",
                      ],
                    ].map(([r, a, b, c]) => (
                      <li key={r} className="flex flex-col gap-1.5">
                        <span className="text-fg-soft">{r}</span>
                        <span className="flex flex-wrap gap-1.5">
                          <Chip>{a}</Chip>
                          <Chip tone={c}>{b}</Chip>
                        </span>
                      </li>
                    ))}
                  </ul>
                </Feature>

                {/* Risks */}
                <Feature
                  kicker="Continuity risk"
                  tone="var(--coral)"
                  title="Gaps found"
                  accent="before they hurt"
                >
                  <p className={body}>
                    Risks come from rules, not vibes: no owner, no backup, a single holder of
                    critical work, stale knowledge. Each risk shows the rule that raised it.
                  </p>
                  <div className={panel}>
                    <span className="text-fg-mute text-xs">Key-person exposure</span>
                    <ul className="mt-3 space-y-2.5 text-xs">
                      {[
                        ["Arjun Rao", "4 critical, sole holder", "var(--coral)"],
                        ["Priya Nair", "2 critical, sole holder", "var(--peri)"],
                        ["Mira Chen", "1 critical, sole holder", "var(--peri)"],
                      ].map(([n, d, c]) => (
                        <li key={n} className="flex items-center justify-between">
                          <span className="text-fg-soft">{n}</span>
                          <span className="tabular-nums" style={{ color: c }}>
                            {d}
                          </span>
                        </li>
                      ))}
                    </ul>
                    <p className="border-line/10 text-fg-mute mt-3 border-t pt-3 text-xs">
                      One click: what if they are away?
                    </p>
                  </div>
                </Feature>

                {/* What If */}
                <Feature
                  kicker="What If? simulator"
                  tone="var(--peri)"
                  title="See the"
                  accent="blast radius"
                >
                  <p className={body}>
                    Deterministic and read-only. An absence is propagated across dependencies,
                    deadlines in the window are listed, and a readiness score shows the rule behind
                    every point.
                  </p>
                  <div className={panel}>
                    <span className="text-fg-mute text-xs">Cover candidates</span>
                    <ul className="mt-3 space-y-3 text-xs">
                      {[
                        ["Dev Patel", 88, "var(--ac)", "Overloaded: 2.4x typical load"],
                        ["Leo Martins", 61, "var(--peri)", ""],
                        ["Sam Okafor", 44, "var(--coral)", ""],
                      ].map(([n, v, c, flag]) => (
                        <li key={n as string}>
                          <div className="flex items-center justify-between">
                            <span className="text-fg-soft">{n}</span>
                            <span className="tabular-nums" style={{ color: c as string }}>
                              {v}%
                            </span>
                          </div>
                          <div className="bg-line/[0.07] mt-1.5 h-1 overflow-clip rounded-full">
                            <div
                              className="h-full rounded-full"
                              style={{ width: `${v}%`, background: c as string }}
                            />
                          </div>
                          {flag ? <p className="text-peri mt-1 text-xs">{flag as string}</p> : null}
                        </li>
                      ))}
                    </ul>
                    <p className="border-line/10 text-fg-mute mt-3 border-t pt-3 text-xs">
                      Overload when load ≥ max(2x typical, typical + 3)
                    </p>
                  </div>
                </Feature>

                {/* Memory replay */}
                <Feature
                  id="memory"
                  className="lg:col-span-2"
                  kicker="Project memory replay"
                  tone="var(--ac)"
                  title="Learn how the work"
                  accent="got here"
                >
                  <div className="mt-2 grid gap-8 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
                    <div>
                      <p className={body}>
                        GitHub, Linear, Notion and Relay events for one responsibility, merged into
                        a single timeline. Filter by incident, press replay, inspect any event, and
                        let AI group it into chapters labelled <em>Inferred</em>.
                      </p>
                      <p className="border-ac/60 text-fg-soft border-l-2 pl-3 text-sm">
                        &ldquo;Why does every payments-api deploy need a canary?&rdquo;
                        <span className="text-fg-mute mt-1 block text-xs">
                          Answers cite events, or say they cannot find one.
                        </span>
                      </p>
                    </div>
                    <MemoryReplayPreview />
                  </div>
                </Feature>

                {/* Handover copilot */}
                <Feature
                  kicker="Handover brief"
                  tone="var(--ac)"
                  title="A brief that shows"
                  accent="its work"
                >
                  <p className={body}>
                    Built per recipient. Every statement is labelled Fact, Rule or AI inference with
                    its evidence, and coverage shows which critical work has a cited statement.
                  </p>
                  <ul className={`${panel} space-y-2.5 text-xs`}>
                    {[
                      ["Fact", "3 open PRs on deploy-pipelines", "var(--peri)"],
                      ["Rule", "No written rollback procedure", "var(--peri)"],
                      ["AI inference", "Old runbook skips the canary", "var(--ac)"],
                    ].map(([l, t, c]) => (
                      <li key={t} className="flex items-center gap-2">
                        <Chip tone={c}>{l}</Chip>
                        <span className="text-fg-soft">{t}</span>
                      </li>
                    ))}
                    <li className="border-line/10 text-fg-mute flex items-center justify-between border-t pt-2.5 text-xs">
                      <span>Coverage 6 of 7 cited</span>
                      <span className="text-peri">1 source changed</span>
                    </li>
                  </ul>
                </Feature>

                {/* Interview */}
                <Feature
                  kicker="Handover interview"
                  tone="var(--ac)"
                  title="Capture what's"
                  accent="in their head"
                >
                  <p className={body}>
                    AI proposes targeted questions from the gaps in the evidence. The outgoing owner
                    answers, a reviewer approves, and answers become knowledge. A coverage gap links
                    straight to the question that closes it.
                  </p>
                  <p className="border-ac/70 text-fg-soft mt-auto border-l-2 pl-4 text-sm leading-relaxed italic">
                    &ldquo;Two runbooks disagree on canary. Which one is current, and why?&rdquo;
                  </p>
                </Feature>

                {/* Audited cases */}
                <Feature
                  kicker="Audited cases"
                  tone="var(--ac)"
                  title="Approval that"
                  accent="means something"
                >
                  <p className={body}>
                    Plan, approve, execute, verify. Critical work needs a second person: separation
                    of duties is checked on completion. Edit a brief and it becomes a new version
                    the recipient must acknowledge again.
                  </p>
                  <ol className={`${panel} space-y-2 text-xs`}>
                    {[
                      ["Approved", "Engineering VP", true],
                      ["Acknowledged v2", "Dev Patel", true],
                      ["Ownership moves", "24 Nov", false],
                    ].map(([l, m, d]) => (
                      <li key={l as string} className="flex items-center justify-between">
                        <span className={d ? "text-fg-soft" : "text-fg-mute"}>
                          {d ? "✓ " : "○ "}
                          {l as string}
                        </span>
                        <span className="text-fg-mute text-xs">{m as string}</span>
                      </li>
                    ))}
                  </ol>
                </Feature>

                {/* Follow-through */}
                <Feature
                  kicker="Follow-through"
                  tone="var(--peri)"
                  title="Did it take"
                  accent="hold?"
                >
                  <p className={body}>
                    We found no other product that checks this. After a handover, each
                    responsibility shows whether the new holder is recorded, reviewing, active and
                    closing tasks. It measures the work, not the person.
                  </p>
                  <ul className={`${panel} flex flex-wrap gap-2`}>
                    <Chip tone="var(--ac)">Settled</Chip>
                    <Chip tone="var(--peri)">Settling in</Chip>
                    <Chip tone="var(--peri)">Check in</Chip>
                    <Chip tone="var(--coral)">New holder not recorded</Chip>
                  </ul>
                </Feature>
              </div>
            </div>
          </section>

          {/* WALKTHROUGH */}
          <section
            id="how"
            className="relative snap-start snap-always scroll-mt-12 py-20 md:mt-14 md:py-24"
          >
            <div className="relative mx-auto max-w-7xl px-6 sm:px-8 lg:px-12">
              <div className="flex flex-col justify-between gap-6 md:flex-row md:items-end">
                <SectionHeading
                  theme="blue"
                  align="left"
                  eyebrow="See it run"
                  title="Arjun gives notice."
                  accent="Here's what happens."
                />
                <p className="scrim reveal text-fg-mute max-w-sm text-sm leading-relaxed">
                  Five steps from the departure signal to a verified successor. Click any step or
                  let it advance.
                </p>
              </div>
              <div className="reveal mt-12 md:mt-14">
                <Walkthrough />
              </div>
            </div>
          </section>

          {/* EVIDENCE */}
          <section
            id="evidence"
            className="relative snap-start snap-always scroll-mt-12 py-20 md:mt-14 md:py-24"
          >
            <div className="relative mx-auto max-w-7xl px-6 sm:px-8 lg:px-12">
              <div className="flex flex-col justify-between gap-6 md:flex-row md:items-end">
                <SectionHeading
                  theme="blue"
                  align="left"
                  eyebrow="Evidence"
                  title="Read-only, from the tools"
                  accent="you already use."
                />
                <p className="reveal scrim text-fg-mute max-w-sm text-sm leading-relaxed">
                  Relay never asks you to move your work. It reads what is already there, and it is
                  explicit about what it never touches.
                </p>
              </div>
              <div className="mt-12 grid gap-5 md:mt-14 md:grid-cols-3">
                {SOURCES.map((s) => (
                  <div key={s.name} className="glass reveal flex flex-col p-7">
                    <span className="font-display text-strong text-5xl leading-[0.95]">
                      {s.name}
                    </span>
                    <span className="text-ac mt-2 text-xs">{s.how}</span>
                    <ul className="text-fg-soft mt-6 space-y-3 text-sm">
                      {s.reads.map((r) => (
                        <li key={r} className="flex gap-2.5">
                          <span className="bg-lime mt-2 h-1 w-1 shrink-0 rounded-full" />
                          {r}
                        </li>
                      ))}
                    </ul>
                    <p className="border-line/10 text-fg-mute mt-auto border-t pt-5 text-xs leading-relaxed">
                      <span className="text-coral">Boundary </span>
                      {s.never}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </section>

          {/* AI PRINCIPLES */}
          <section
            id="ai"
            className="relative snap-start snap-always scroll-mt-12 py-20 md:mt-14 md:py-24"
          >
            <div className="relative mx-auto max-w-7xl px-6 sm:px-8 lg:px-12">
              <div className="flex flex-col justify-between gap-6 md:flex-row md:items-end">
                <SectionHeading
                  theme="blue"
                  align="left"
                  eyebrow="AI you can defend"
                  title="Rules decide. AI explains."
                  accent="People approve."
                />
                <p className="reveal scrim text-fg-mute max-w-sm text-sm leading-relaxed">
                  Deterministic where it decides, generative where it explains. If AI is switched
                  off, nothing breaks: you get labelled search and rule-based briefs.
                </p>
              </div>
              <div className="glass md:divide-line/10 mt-12 grid overflow-clip md:mt-14 md:grid-cols-3 md:divide-x">
                {PRINCIPLES.map((p) => (
                  <div key={p.num} className="reveal p-8">
                    <span
                      className="font-bebas text-7xl leading-none"
                      style={{ color: "transparent", WebkitTextStroke: `1.5px ${p.tone}` }}
                    >
                      {p.num}
                    </span>
                    <h3 className="font-display text-strong mt-4 text-4xl">{p.title}</h3>
                    <ul className="text-fg-mute mt-5 space-y-3 text-sm leading-relaxed">
                      {p.points.map((t) => (
                        <li key={t} className="flex gap-2.5">
                          <span
                            className="mt-2 h-1 w-1 shrink-0 rounded-full"
                            style={{ background: p.tone }}
                          />
                          {t}
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>

              <div className="mt-5 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
                {EVAL.map((e) => (
                  <div key={e.label} className="glass reveal p-6">
                    <span className="font-bebas text-ac text-6xl leading-none">{e.value}</span>
                    <p className="text-fg-soft mt-3 text-sm font-medium">{e.label}</p>
                    <p className="text-fg-mute mt-1 text-xs">{e.sub}</p>
                  </div>
                ))}
              </div>
              <p className="text-fg-mute mt-4 text-xs">
                Scripted evaluation run in CI against synthetic cases. The same cases can run
                against a live model.
              </p>
            </div>
          </section>

          {/* TRUST */}
          <section
            id="trust"
            className="relative snap-start snap-always scroll-mt-12 py-20 md:mt-14 md:py-24"
          >
            <div className="relative mx-auto grid max-w-7xl gap-14 px-6 sm:px-8 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.3fr)] lg:px-12">
              <div className="lg:sticky lg:top-28 lg:self-start">
                <SectionHeading
                  theme="blue"
                  align="left"
                  compact
                  eyebrow="Trust"
                  title="Safe by"
                  accent="construction."
                  description="Continuity data is sensitive. Relay is built so the safe path is the only path, and the database enforces it, not just the application."
                />
              </div>
              <ul className="glass divide-line/10 divide-y px-7">
                {SPEC.map((p) => {
                  const Icon = p.icon;
                  return (
                    <li key={p.code} className="reveal flex gap-6 py-8">
                      <div className="border-line/10 bg-line/[0.04] text-ac flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border">
                        <Icon className="h-5 w-5" />
                      </div>
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-3">
                          <span className="text-fg-mute text-xs">{p.code}</span>
                          <span className="text-ac border-ac/25 bg-ac/10 rounded-full border px-2.5 py-0.5 text-xs">
                            {p.spec}
                          </span>
                        </div>
                        <h3 className="text-strong mt-3 text-xl leading-snug font-semibold sm:text-2xl">
                          {p.title}
                        </h3>
                        <p className="text-fg-mute mt-3 text-[0.95rem] leading-relaxed">{p.desc}</p>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </div>
          </section>

          {/* PROOF */}
          <section className="relative snap-start snap-always py-24">
            <div className="relative mx-auto max-w-7xl px-6 sm:px-8 lg:px-12">
              <div className="glass lg:divide-line/10 grid overflow-clip sm:grid-cols-2 lg:grid-cols-4 lg:divide-x">
                {PROOF.map((p) => (
                  <div key={p.label} className="reveal p-8">
                    <span className="font-bebas text-strong text-[4.5rem] leading-none">
                      {p.value}
                    </span>
                    <p className="text-fg-soft mt-3 text-sm font-medium">{p.label}</p>
                    <p className="text-fg-mute mt-1 text-xs leading-relaxed">{p.sub}</p>
                  </div>
                ))}
              </div>
            </div>
          </section>

          {/* TRY IT */}
          <section
            id="try"
            className="relative snap-start snap-always scroll-mt-12 py-20 md:mt-14 md:py-24"
          >
            <div className="relative mx-auto grid max-w-7xl gap-14 px-6 sm:px-8 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.3fr)] lg:px-12">
              <div className="lg:sticky lg:top-28 lg:self-start">
                <SectionHeading
                  theme="blue"
                  align="left"
                  compact
                  eyebrow="Try it"
                  title="Ten minutes,"
                  accent="no setup."
                  description="Sign in with any email. Relay sends a one-time code and never sees a password."
                />
                <p className="reveal glass-clear text-fg-mute mt-8 rounded-xl p-4 text-xs leading-relaxed">
                  <span className="text-peri">Honest limits </span>
                  The sample workspace&apos;s GitHub, Linear and Notion records are synthetic and
                  labelled as such. AI prose needs a configured model, otherwise Relay falls back to
                  rule-based briefs. Brief coverage matches by name, so it shows a gap to check,
                  never a verdict.
                </p>
              </div>
              <ol className="glass divide-line/10 divide-y px-7">
                {TRY.map(([t, d], i) => (
                  <li
                    key={t}
                    className="reveal border-line/10 grid grid-cols-[4rem_minmax(0,1fr)] gap-4 border-b py-7 last:border-b-0"
                  >
                    <span className="font-bebas display-outline text-5xl leading-none tracking-wider">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <div>
                      <h3 className="text-strong text-xl font-semibold">{t}</h3>
                      <p className="text-fg-mute mt-2 text-[0.95rem] leading-relaxed">{d}</p>
                    </div>
                  </li>
                ))}
              </ol>
            </div>
          </section>

          {/* CLOSING CTA */}
          <section className="bg-page relative snap-start snap-always overflow-clip py-32 sm:py-40">
            <div aria-hidden className="pointer-events-none absolute inset-0">
              <div className="absolute top-1/2 right-[6%] h-[560px] w-[640px] -translate-y-1/2 rounded-full bg-[radial-gradient(ellipse_at_center,rgba(46,84,230,0.38),transparent_68%)] blur-3xl" />
              <Petals
                className="absolute inset-y-0 right-0 h-full w-full opacity-90 lg:w-[72%]"
                petals={[
                  { x: 640, y: 790, rot: -78, s: 1.0, o: 0.7, blur: true },
                  { x: 700, y: 800, rot: -34, s: 1.25, o: 0.95 },
                  { x: 820, y: 810, rot: 8, s: 1.4, o: 1 },
                  { x: 940, y: 800, rot: 46, s: 1.2, o: 0.9 },
                  { x: 1040, y: 780, rot: 78, s: 1.0, o: 0.7, blur: true },
                ]}
              />
              <div className="absolute top-[46%] right-[27%] h-28 w-44 -rotate-[14deg] rounded-[60%] bg-[radial-gradient(ellipse_at_center,var(--orb-glow),transparent_72%)] blur-xl" />
              <div className="from-page via-page/80 absolute inset-0 bg-gradient-to-r to-transparent" />
              <div className="from-page to-page absolute inset-0 bg-gradient-to-b via-transparent" />
            </div>

            <div className="reveal relative mx-auto max-w-7xl px-6 sm:px-8 lg:px-12">
              <div className="max-w-xl">
                <span className="text-peri text-sm font-medium">Try Relay</span>
                <h2 className="mt-5">
                  <span className="font-display text-ac block text-[clamp(4rem,10vw,8.5rem)] leading-[0.9] tracking-[-0.02em] italic">
                    Pass the
                  </span>
                  <span className="font-display text-strong block text-[clamp(3rem,7.4vw,6.4rem)] leading-[0.95] tracking-[-0.01em]">
                    accountability.
                  </span>
                  <span className="text-peri mt-2 block text-[clamp(1.6rem,3.6vw,3rem)] leading-tight font-light tracking-tight">
                    And prove it happened.
                  </span>
                </h2>
                <p className="text-fg-soft mt-8 max-w-md text-base leading-relaxed">
                  Open the sample workspace and run a handover end to end: replay the history,
                  simulate the absence, brief the successor, and check it took hold.
                </p>
                <div className="mt-10 flex flex-wrap items-center gap-4">
                  <Link
                    href="/workspaces"
                    className="group bg-cta text-cta-fg hover:bg-cta-hover inline-flex h-12 items-center gap-2 rounded-full px-7 text-sm font-semibold transition-colors"
                  >
                    Open the sample workspace
                    <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
                  </Link>
                  <a
                    href={REPO_URL}
                    className="border-line/25 text-fg-soft hover:border-line/50 hover:text-strong inline-flex h-12 items-center gap-2 rounded-full border px-7 text-sm font-medium transition-colors"
                  >
                    View the source
                    <ArrowUpRight className="h-4 w-4" aria-hidden />
                  </a>
                </div>
                <p className="text-fg-mute mt-8 text-sm">
                  Read-only integrations. Forced row-level security. A complete audit trail.
                </p>
              </div>
            </div>
          </section>
        </div>
      </div>
    </>
  );
}

export function LandingFooter() {
  return (
    <footer className="border-line/[0.08] bg-page relative snap-start snap-always overflow-clip border-t">
      <div className="relative z-10 mx-auto grid max-w-7xl gap-10 px-6 pt-16 pb-6 sm:px-8 md:grid-cols-[1.4fr_1fr_1fr] lg:px-12">
        <div>
          <div className="flex items-center gap-2.5">
            <RelayMark className="h-7 w-7" />
            <span className="text-strong text-xl font-medium tracking-tight">Relay</span>
          </div>
          <p className="text-fg-mute mt-4 max-w-xs text-sm leading-relaxed">
            Relay makes accountability transferable, and proves the transfer happened.
          </p>
        </div>
        <nav aria-label="Product" className="text-fg-mute flex flex-col gap-3 text-sm">
          <span className="text-fg-mute text-xs">Product</span>
          <a href="#product" className="hover:text-strong transition-colors">
            Features
          </a>
          <a href="#simulator" className="hover:text-strong transition-colors">
            What If? simulator
          </a>
          <a href="#evidence" className="hover:text-strong transition-colors">
            Evidence sources
          </a>
          <a href="#ai" className="hover:text-strong transition-colors">
            AI guardrails
          </a>
          <a href="#trust" className="hover:text-strong transition-colors">
            Trust and security
          </a>
        </nav>
        <nav aria-label="Explore" className="text-fg-mute flex flex-col gap-3 text-sm">
          <span className="text-fg-mute text-xs">Explore</span>
          <Link href="/workspaces" className="hover:text-strong transition-colors">
            Sample workspace
          </Link>
          <a href="#try" className="hover:text-strong transition-colors">
            Ten-minute tour
          </a>
          <a href={REPO_URL} className="hover:text-strong transition-colors">
            Source on GitHub
          </a>
          <a href="/llms.txt" className="hover:text-strong transition-colors">
            llms.txt
          </a>
        </nav>
      </div>

      {/* Giant wordmark: complete glyphs, edge-lit, with a lime glow underneath */}
      <div aria-hidden className="pointer-events-none relative mt-10 select-none">
        <div className="wordmark-glow absolute inset-x-[10%] bottom-0 h-1/2 blur-3xl" />
        <span className="wordmark font-bebas relative block pb-[0.08em] text-center text-[clamp(8rem,27vw,25rem)] leading-[0.86] tracking-[0.05em]">
          RELAY
        </span>
      </div>

      <div className="border-line/[0.06] relative z-10 border-t">
        <div className="text-fg-mute mx-auto flex max-w-7xl flex-col items-center justify-between gap-2 px-6 py-5 text-xs sm:flex-row sm:px-8 lg:px-12">
          <span>© 2026 Relay Systems. All rights reserved.</span>
          <span>AI proposes, people decide</span>
        </div>
      </div>
    </footer>
  );
}
