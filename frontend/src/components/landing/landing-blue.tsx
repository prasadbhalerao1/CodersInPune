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
    tone: "#FF6B7A",
    points: [
      "Risks, readiness, simulation and overload are deterministic rules you can read on the page.",
      "Missing owners, stale knowledge and conflicting runbooks are found before any model runs.",
    ],
  },
  {
    num: "02",
    title: "AI explains",
    tone: "#B8FF3C",
    points: [
      "Every AI statement cites evidence Relay validates, or it is dropped. A conflict needs two sources.",
      "Models hold read-only tools. They cannot change ownership, approve, acknowledge or edit a source.",
    ],
  },
  {
    num: "03",
    title: "People approve",
    tone: "#B8FF3C",
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
  return (
    <div
      aria-hidden
      className={`absolute rounded-full ${className}`}
      style={{
        background:
          "radial-gradient(circle at 32% 28%, #F6FFC9 0%, #CFFF5E 20%, #B8FF3C 44%, #6F9A12 80%, #2A4008 100%)",
        boxShadow:
          "0 0 90px 12px rgba(184,255,60,0.22), inset -14px -18px 34px rgba(0,0,0,0.35), inset 10px 10px 24px rgba(255,255,255,0.25)",
      }}
    />
  );
}

/** What the glass refracts: orchid petals and lime glass orbs, spread down the page. */
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
    <div aria-hidden className="layer pointer-events-none absolute inset-0 z-0 overflow-hidden">
      {clusters.map(([pos, flip]) => (
        <Petals key={pos} className={`${sizes} ${pos} opacity-75`} petals={cluster(flip)} />
      ))}
      {orbs.map((o) => (
        <Orb key={o} className={o} />
      ))}
    </div>
  );
}

/** The second half of the page: cobalt, periwinkle and acid lime, in serif. */
export function BlueHalf() {
  return (
    <>
      {/* SIMULATOR */}
      <section
        id="simulator"
        className="relative scroll-mt-16 overflow-hidden border-b border-white/[0.08] py-28"
      >
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{
            clipPath: "polygon(52% 0%, 100% 0%, 100% 100%, 30% 100%)",
            background:
              "linear-gradient(160deg, #8E1626 0%, #5B1F6B 34%, #26308F 66%, #1B3FD0 100%)",
            opacity: 0.5,
          }}
        />
        <div
          aria-hidden
          className="pointer-events-none absolute top-1/2 right-[8%] h-[520px] w-[640px] -translate-y-1/2 bg-[radial-gradient(ellipse_at_center,rgba(184,255,60,0.12),transparent_65%)] blur-3xl"
        />
        <div className="relative mx-auto grid max-w-7xl items-center gap-14 px-6 sm:px-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,34rem)] lg:px-12">
          <div>
            <SectionHeading
              theme="blue"
              align="left"
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
                  <span className="text-lg text-slate-200">{t}</span>
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
          <section id="product" className="relative scroll-mt-16 py-28">
            <div className="relative mx-auto max-w-7xl px-6 sm:px-8 lg:px-12">
              <SectionHeading
                theme="blue"
                eyebrow="The product"
                title="Everything a handover"
                accent="actually needs."
                description="Eight capabilities, built to hand off to each other. The people and numbers on these cards are the synthetic Northwind Labs sample."
              />

              <div className="mt-16 grid gap-5 lg:grid-cols-3">
                {/* Accountability map */}
                <Feature
                  kicker="Accountability map"
                  tone="#B8FF3C"
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
                      ["Production deployments", "Arjun · primary", "Leo · backup", "#B8FF3C"],
                      ["Vendor contract renewal", "Priya · primary", "No backup", "#FF6B7A"],
                      ["Quarterly compliance export", "Mira · primary", "Review due", "#8FA8FF"],
                    ].map(([r, a, b, c]) => (
                      <li key={r} className="flex flex-col gap-1.5">
                        <span className="text-slate-200">{r}</span>
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
                  tone="#FF6B7A"
                  title="Gaps found"
                  accent="before they hurt"
                >
                  <p className={body}>
                    Risks come from rules, not vibes: no owner, no backup, a single holder of
                    critical work, stale knowledge. Each risk shows the rule that raised it.
                  </p>
                  <div className={panel}>
                    <span className="text-xs text-slate-500">Key-person exposure</span>
                    <ul className="mt-3 space-y-2.5 text-xs">
                      {[
                        ["Arjun Rao", "4 critical, sole holder", "#FF6B7A"],
                        ["Priya Nair", "2 critical, sole holder", "#8FA8FF"],
                        ["Mira Chen", "1 critical, sole holder", "#8FA8FF"],
                      ].map(([n, d, c]) => (
                        <li key={n} className="flex items-center justify-between">
                          <span className="text-slate-200">{n}</span>
                          <span className="tabular-nums" style={{ color: c }}>
                            {d}
                          </span>
                        </li>
                      ))}
                    </ul>
                    <p className="mt-3 border-t border-white/10 pt-3 text-xs text-slate-500">
                      One click: what if they are away?
                    </p>
                  </div>
                </Feature>

                {/* What If */}
                <Feature
                  kicker="What If? simulator"
                  tone="#8FA8FF"
                  title="See the"
                  accent="blast radius"
                >
                  <p className={body}>
                    Deterministic and read-only. An absence is propagated across dependencies,
                    deadlines in the window are listed, and a readiness score shows the rule behind
                    every point.
                  </p>
                  <div className={panel}>
                    <span className="text-xs text-slate-500">Cover candidates</span>
                    <ul className="mt-3 space-y-3 text-xs">
                      {[
                        ["Dev Patel", 88, "#B8FF3C", "Overloaded: 2.4x typical load"],
                        ["Leo Martins", 61, "#8FA8FF", ""],
                        ["Sam Okafor", 44, "#FF6B7A", ""],
                      ].map(([n, v, c, flag]) => (
                        <li key={n as string}>
                          <div className="flex items-center justify-between">
                            <span className="text-slate-200">{n}</span>
                            <span className="tabular-nums" style={{ color: c as string }}>
                              {v}%
                            </span>
                          </div>
                          <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-white/[0.07]">
                            <div
                              className="h-full rounded-full"
                              style={{ width: `${v}%`, background: c as string }}
                            />
                          </div>
                          {flag ? (
                            <p className="mt-1 text-[10px] text-indigo-400">{flag as string}</p>
                          ) : null}
                        </li>
                      ))}
                    </ul>
                    <p className="mt-3 border-t border-white/10 pt-3 text-xs text-slate-500">
                      Overload when load ≥ max(2x typical, typical + 3)
                    </p>
                  </div>
                </Feature>

                {/* Memory replay */}
                <Feature
                  id="memory"
                  className="lg:col-span-2"
                  kicker="Project memory replay"
                  tone="#B8FF3C"
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
                      <p className="mt-4 rounded-lg border border-white/10 bg-black/30 p-3 text-sm text-slate-300">
                        &ldquo;Why does every payments-api deploy need a canary?&rdquo;
                        <span className="mt-1 block text-xs text-slate-500">
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
                  tone="#B8FF3C"
                  title="A brief that shows"
                  accent="its work"
                >
                  <p className={body}>
                    Built per recipient. Every statement is labelled Fact, Rule or AI inference with
                    its evidence, and coverage shows which critical work has a cited statement.
                  </p>
                  <ul className={`${panel} space-y-2.5 text-xs`}>
                    {[
                      ["Fact", "3 open PRs on deploy-pipelines", "#8FA8FF"],
                      ["Rule", "No written rollback procedure", "#8FA8FF"],
                      ["AI inference", "Old runbook skips the canary", "#B8FF3C"],
                    ].map(([l, t, c]) => (
                      <li key={t} className="flex items-center gap-2">
                        <Chip tone={c}>{l}</Chip>
                        <span className="text-slate-300">{t}</span>
                      </li>
                    ))}
                    <li className="flex items-center justify-between border-t border-white/10 pt-2.5 text-xs text-slate-500">
                      <span>Coverage 6 of 7 cited</span>
                      <span className="text-indigo-400">1 source changed</span>
                    </li>
                  </ul>
                </Feature>

                {/* Interview */}
                <Feature
                  kicker="Handover interview"
                  tone="#B8FF3C"
                  title="Capture what's"
                  accent="in their head"
                >
                  <p className={body}>
                    AI proposes targeted questions from the gaps in the evidence. The outgoing owner
                    answers, a reviewer approves, and answers become knowledge. A coverage gap links
                    straight to the question that closes it.
                  </p>
                  <p className="mt-5 rounded-xl border border-white/10 bg-black/40 p-4 text-sm text-slate-300">
                    &ldquo;Two runbooks disagree on canary. Which one is current, and why?&rdquo;
                  </p>
                </Feature>

                {/* Audited cases */}
                <Feature
                  kicker="Audited cases"
                  tone="#B8FF3C"
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
                        <span className={d ? "text-slate-200" : "text-slate-500"}>
                          {d ? "✓ " : "○ "}
                          {l as string}
                        </span>
                        <span className="text-xs text-slate-500">{m as string}</span>
                      </li>
                    ))}
                  </ol>
                </Feature>

                {/* Follow-through */}
                <Feature kicker="Follow-through" tone="#8FA8FF" title="Did it take" accent="hold?">
                  <p className={body}>
                    We found no other product that checks this. After a handover, each
                    responsibility shows whether the new holder is recorded, reviewing, active and
                    closing tasks. It measures the work, not the person.
                  </p>
                  <ul className={`${panel} flex flex-wrap gap-2`}>
                    <Chip tone="#B8FF3C">Settled</Chip>
                    <Chip tone="#8FA8FF">Settling in</Chip>
                    <Chip tone="#8FA8FF">Check in</Chip>
                    <Chip tone="#FF6B7A">New holder not recorded</Chip>
                  </ul>
                </Feature>
              </div>
            </div>
          </section>

          {/* WALKTHROUGH */}
          <section id="how" className="relative scroll-mt-16 py-28">
            <div className="relative mx-auto max-w-7xl px-6 sm:px-8 lg:px-12">
              <div className="flex flex-col justify-between gap-6 md:flex-row md:items-end">
                <SectionHeading
                  theme="blue"
                  align="left"
                  eyebrow="See it run"
                  title="Arjun gives notice."
                  accent="Here's what happens."
                />
                <p className="reveal max-w-sm text-sm leading-relaxed text-slate-400">
                  Five steps from the departure signal to a verified successor. Click any step or
                  let it advance.
                </p>
              </div>
              <div className="reveal mt-14">
                <Walkthrough />
              </div>
            </div>
          </section>

          {/* EVIDENCE */}
          <section id="evidence" className="relative scroll-mt-16 py-28">
            <div className="relative mx-auto max-w-7xl px-6 sm:px-8 lg:px-12">
              <SectionHeading
                theme="blue"
                eyebrow="Evidence"
                title="Read-only, from the tools"
                accent="you already use."
                description="Relay never asks you to move your work. It reads what is already there, and it is explicit about what it never touches."
              />
              <div className="mt-16 grid gap-5 md:grid-cols-3">
                {SOURCES.map((s) => (
                  <div key={s.name} className="glass reveal flex flex-col p-7">
                    <span className="font-display text-5xl leading-[0.95] text-[#F2EEE5]">
                      {s.name}
                    </span>
                    <span className="mt-2 text-xs text-[#B8FF3C]">{s.how}</span>
                    <ul className="mt-6 space-y-3 text-sm text-slate-300">
                      {s.reads.map((r) => (
                        <li key={r} className="flex gap-2.5">
                          <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-[#B8FF3C]" />
                          {r}
                        </li>
                      ))}
                    </ul>
                    <p className="mt-auto border-t border-white/10 pt-5 text-xs leading-relaxed text-slate-500">
                      <span className="text-[#FF6B7A]">Boundary </span>
                      {s.never}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </section>

          {/* AI PRINCIPLES */}
          <section id="ai" className="relative scroll-mt-16 py-28">
            <div className="relative mx-auto max-w-7xl px-6 sm:px-8 lg:px-12">
              <SectionHeading
                theme="blue"
                eyebrow="AI you can defend"
                title="Rules decide. AI explains."
                accent="People approve."
                description="Deterministic where it decides, generative where it explains. If AI is switched off, nothing breaks: you get labelled search and rule-based briefs."
              />
              <div className="glass mt-16 grid overflow-hidden md:grid-cols-3 md:divide-x md:divide-white/10">
                {PRINCIPLES.map((p) => (
                  <div key={p.num} className="reveal p-8">
                    <span
                      className="font-bebas text-7xl leading-none"
                      style={{ color: "transparent", WebkitTextStroke: `1.5px ${p.tone}` }}
                    >
                      {p.num}
                    </span>
                    <h3 className="font-display mt-4 text-4xl text-[#F2EEE5]">{p.title}</h3>
                    <ul className="mt-5 space-y-3 text-sm leading-relaxed text-slate-400">
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
                    <span className="font-bebas text-6xl leading-none text-[#B8FF3C]">
                      {e.value}
                    </span>
                    <p className="mt-3 text-sm font-medium text-slate-200">{e.label}</p>
                    <p className="mt-1 text-xs text-slate-500">{e.sub}</p>
                  </div>
                ))}
              </div>
              <p className="mt-4 text-xs text-slate-600">
                Scripted evaluation run in CI against synthetic cases. The same cases can run
                against a live model.
              </p>
            </div>
          </section>

          {/* TRUST */}
          <section id="trust" className="relative scroll-mt-16 py-28">
            <div className="relative mx-auto grid max-w-7xl gap-14 px-6 sm:px-8 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.3fr)] lg:px-12">
              <div className="lg:sticky lg:top-28 lg:self-start">
                <SectionHeading
                  theme="blue"
                  align="left"
                  eyebrow="Trust"
                  title="Safe by"
                  accent="construction."
                  description="Continuity data is sensitive. Relay is built so the safe path is the only path, and the database enforces it, not just the application."
                />
              </div>
              <ul className="glass divide-y divide-white/10 px-7">
                {SPEC.map((p) => {
                  const Icon = p.icon;
                  return (
                    <li key={p.code} className="reveal group flex gap-6 py-8">
                      <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] text-[#B8FF3C] transition-colors group-hover:border-[#B8FF3C]/40">
                        <Icon className="h-5 w-5" />
                      </div>
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-3">
                          <span className="text-xs text-slate-500">{p.code}</span>
                          <span className="rounded-full border border-lime-500/25 bg-lime-500/10 px-2.5 py-0.5 text-xs text-lime-400">
                            {p.spec}
                          </span>
                        </div>
                        <h3 className="mt-3 text-xl leading-snug font-semibold text-[#F2EEE5] sm:text-2xl">
                          {p.title}
                        </h3>
                        <p className="mt-3 text-[0.95rem] leading-relaxed text-slate-400">
                          {p.desc}
                        </p>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </div>
          </section>

          {/* PROOF */}
          <section className="relative py-24">
            <div className="relative mx-auto max-w-7xl px-6 sm:px-8 lg:px-12">
              <div className="glass grid overflow-hidden sm:grid-cols-2 lg:grid-cols-4 lg:divide-x lg:divide-white/10">
                {PROOF.map((p) => (
                  <div key={p.label} className="reveal p-8">
                    <span className="font-bebas text-[4.5rem] leading-none text-[#F2EEE5]">
                      {p.value}
                    </span>
                    <p className="mt-3 text-sm font-medium text-slate-200">{p.label}</p>
                    <p className="mt-1 text-xs leading-relaxed text-slate-500">{p.sub}</p>
                  </div>
                ))}
              </div>
            </div>
          </section>

          {/* TRY IT */}
          <section id="try" className="relative scroll-mt-16 py-28">
            <div className="relative mx-auto grid max-w-7xl gap-14 px-6 sm:px-8 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.3fr)] lg:px-12">
              <div className="lg:sticky lg:top-28 lg:self-start">
                <SectionHeading
                  theme="blue"
                  align="left"
                  eyebrow="Try it"
                  title="Ten minutes,"
                  accent="no setup."
                  description="Sign in with any email. Relay sends a one-time code and never sees a password."
                />
                <p className="reveal glass-clear mt-8 rounded-xl p-4 text-xs leading-relaxed text-slate-500">
                  <span className="text-indigo-400">Honest limits </span>
                  The sample workspace&apos;s GitHub, Linear and Notion records are synthetic and
                  labelled as such. AI prose needs a configured model, otherwise Relay falls back to
                  rule-based briefs. Brief coverage matches by name, so it shows a gap to check,
                  never a verdict.
                </p>
              </div>
              <ol className="glass divide-y divide-white/10 px-7">
                {TRY.map(([t, d], i) => (
                  <li
                    key={t}
                    className="reveal grid grid-cols-[4rem_minmax(0,1fr)] gap-4 border-b border-white/10 py-7 last:border-b-0"
                  >
                    <span className="font-bebas display-outline text-5xl leading-none tracking-wider">
                      {String(i + 1).padStart(2, "0")}
                    </span>
                    <div>
                      <h3 className="text-xl font-semibold text-[#F2EEE5]">{t}</h3>
                      <p className="mt-2 text-[0.95rem] leading-relaxed text-slate-400">{d}</p>
                    </div>
                  </li>
                ))}
              </ol>
            </div>
          </section>

          {/* CLOSING CTA */}
          <section className="relative overflow-hidden bg-[#03050D] py-32 sm:py-40">
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
              <div className="absolute top-[46%] right-[27%] h-28 w-44 -rotate-[14deg] rounded-[60%] bg-[radial-gradient(ellipse_at_center,rgba(184,255,60,0.55),rgba(184,255,60,0.12)_55%,transparent_75%)] blur-xl" />
              <div className="absolute inset-0 bg-gradient-to-r from-[#03050D] via-[#03050D]/80 to-transparent" />
              <div className="absolute inset-0 bg-gradient-to-b from-[#050A1C] via-transparent to-[#03050D]" />
            </div>

            <div className="reveal relative mx-auto max-w-7xl px-6 sm:px-8 lg:px-12">
              <div className="max-w-xl">
                <span className="text-sm font-medium text-[#8FA8FF]">Try Relay</span>
                <h2 className="mt-5">
                  <span className="font-display block text-[clamp(4rem,10vw,8.5rem)] leading-[0.9] tracking-[-0.02em] text-[#B8FF3C] italic">
                    Pass the
                  </span>
                  <span className="font-display block text-[clamp(3rem,7.4vw,6.4rem)] leading-[0.95] tracking-[-0.01em] text-[#F2EEE5]">
                    accountability.
                  </span>
                  <span className="mt-2 block text-[clamp(1.6rem,3.6vw,3rem)] leading-tight font-light tracking-tight text-[#8FA8FF]">
                    And prove it happened.
                  </span>
                </h2>
                <p className="mt-8 max-w-md text-base leading-relaxed text-slate-300">
                  Open the sample workspace and run a handover end to end: replay the history,
                  simulate the absence, brief the successor, and check it took hold.
                </p>
                <div className="mt-10 flex flex-wrap items-center gap-4">
                  <Link
                    href="/workspaces"
                    className="group inline-flex h-12 items-center gap-2 rounded-full bg-[#B8FF3C] px-7 text-sm font-semibold text-[#04060F] transition-colors hover:bg-[#caff6a]"
                  >
                    Open the sample workspace
                    <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
                  </Link>
                  <a
                    href={REPO_URL}
                    className="inline-flex h-12 items-center gap-2 rounded-full border border-white/25 px-7 text-sm font-medium text-slate-200 transition-colors hover:border-white/50 hover:text-white"
                  >
                    View the source
                    <ArrowUpRight className="h-4 w-4" aria-hidden />
                  </a>
                </div>
                <p className="mt-8 text-sm text-slate-500">
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
    <footer className="relative overflow-hidden border-t border-white/[0.08] bg-[#03050D]">
      <div className="relative z-10 mx-auto grid max-w-7xl gap-10 px-6 pt-16 pb-6 sm:px-8 md:grid-cols-[1.4fr_1fr_1fr] lg:px-12">
        <div>
          <div className="flex items-center gap-2.5">
            <RelayMark className="h-7 w-7" />
            <span className="text-xl font-medium tracking-tight text-white">Relay</span>
          </div>
          <p className="mt-4 max-w-xs text-sm leading-relaxed text-slate-500">
            Relay makes accountability transferable, and proves the transfer happened.
          </p>
        </div>
        <nav aria-label="Product" className="flex flex-col gap-3 text-sm text-slate-400">
          <span className="text-xs text-slate-600">Product</span>
          <a href="#product" className="transition-colors hover:text-white">
            Features
          </a>
          <a href="#simulator" className="transition-colors hover:text-white">
            What If? simulator
          </a>
          <a href="#evidence" className="transition-colors hover:text-white">
            Evidence sources
          </a>
          <a href="#ai" className="transition-colors hover:text-white">
            AI guardrails
          </a>
          <a href="#trust" className="transition-colors hover:text-white">
            Trust and security
          </a>
        </nav>
        <nav aria-label="Explore" className="flex flex-col gap-3 text-sm text-slate-400">
          <span className="text-xs text-slate-600">Explore</span>
          <Link href="/workspaces" className="transition-colors hover:text-white">
            Sample workspace
          </Link>
          <a href="#try" className="transition-colors hover:text-white">
            Ten-minute tour
          </a>
          <a href={REPO_URL} className="transition-colors hover:text-white">
            Source on GitHub
          </a>
          <a href="/llms.txt" className="transition-colors hover:text-white">
            llms.txt
          </a>
        </nav>
      </div>

      {/* Giant wordmark: complete glyphs, edge-lit, with a lime glow underneath */}
      <div aria-hidden className="pointer-events-none relative mt-10 select-none">
        <div className="absolute inset-x-[10%] bottom-0 h-1/2 bg-[radial-gradient(ellipse_at_center,rgba(184,255,60,0.18),transparent_70%)] blur-3xl" />
        <span
          className="font-bebas relative block pb-[0.08em] text-center text-[clamp(8rem,27vw,25rem)] leading-[0.86] tracking-[0.05em] text-transparent"
          style={{
            WebkitTextStroke: "1.5px rgba(184,255,60,0.75)",
            backgroundImage:
              "linear-gradient(180deg, rgba(143,168,255,0.28) 0%, rgba(59,91,255,0.1) 60%, transparent 100%)",
            WebkitBackgroundClip: "text",
            backgroundClip: "text",
            filter: "drop-shadow(0 0 22px rgba(184,255,60,0.25))",
          }}
        >
          RELAY
        </span>
      </div>

      <div className="relative z-10 border-t border-white/[0.06]">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-2 px-6 py-5 text-xs text-slate-600 sm:flex-row sm:px-8 lg:px-12">
          <span>© 2026 Relay Systems. All rights reserved.</span>
          <span>AI proposes, people decide</span>
        </div>
      </div>
    </footer>
  );
}
