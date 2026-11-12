import { BlueHalf } from "@/components/landing/landing-blue";
import { SectionHeading } from "@/components/landing/section";

/* ──────────────────────────────────────────────────────────────────────────
   Content. Every claim below is taken from the project docs (JUDGE_GUIDE,
   PROJECT_OVERVIEW, competitive-analysis, ai, trust); sample names are synthetic.
   ────────────────────────────────────────────────────────────────────────── */

const MANIFESTO =
  "One person knows the deploy pipeline. Another renews the vendor contract. Then one of them resigns, and nobody can say what breaks.";

const FAILURES = [
  {
    num: "01",
    tag: "No complete list",
    headline: "Nobody knows everything they were accountable for.",
    desc: "Ownership lives in people's heads, half-updated wikis and a CODEOWNERS file nobody reads. The list is reconstructed in a panic during the notice period.",
  },
  {
    num: "02",
    tag: "Scattered context",
    headline: "The why is split across GitHub, Linear, Notion and a person.",
    desc: "Why the canary exists, which runbook is outdated, what was decided in which thread. The successor inherits the artefacts and none of the reasoning.",
  },
  {
    num: "03",
    tag: "Unchecked handover",
    headline: "A document written in the last week, read once, never verified.",
    desc: "Nobody confirms what actually changed hands, whether the new owner understood it, or whether the work kept moving a month later.",
  },
];

const GAP = [
  {
    cat: "Service catalogues",
    owns: "Which team owns which service",
    stops: "Ownership is a field. Handing it to a person, with context, is out of scope.",
  },
  {
    cat: "Knowledge tools",
    owns: "What is written down",
    stops: "Knows the page, not who is accountable or what breaks when they leave.",
  },
  {
    cat: "Work management",
    owns: "Issues and their history",
    stops:
      "History is per ticket. No view of what one person's absence does across all their work.",
  },
  {
    cat: "Incident and on-call",
    owns: "Who responds right now",
    stops: "Covers the rota, not the long tail of responsibilities that never page anyone.",
  },
  {
    cat: "HR offboarding",
    owns: "Access, assets, exit tasks",
    stops: "Knowledge transfer is one checklist item that depends on the leaver's goodwill.",
  },
];

const JOURNEY = [
  {
    phase: "Understand",
    tone: "#B8FF3C",
    steps: ["Memory Replay: how the work got here"],
  },
  {
    phase: "Forecast",
    tone: "#FF6B7A",
    steps: ["What If? absence simulation", "Cover candidates and overload"],
  },
  {
    phase: "Decide",
    tone: "#8FA8FF",
    steps: ["Pick a successor", "Open a pre-filled handover case"],
  },
  {
    phase: "Transfer",
    tone: "#B8FF3C",
    steps: [
      "Handover Brief and interview",
      "Approve a version",
      "Recipient acknowledges",
      "Execute",
    ],
  },
  {
    phase: "Prove",
    tone: "#8FA8FF",
    steps: ["Separation-of-duties check", "Follow-through: did it take hold?"],
  },
];

/* ──────────────────────────────────────────────────────────────────────────
   Small building blocks
   ────────────────────────────────────────────────────────────────────────── */

/** Everything below the hero. */
export function LandingSections() {
  const words = MANIFESTO.split(" ");
  return (
    <>
      {/* What it connects to */}
      <div className="border-y border-white/[0.08] bg-white/[0.03] py-4 backdrop-blur-md">
        <p className="mx-auto max-w-7xl px-6 text-center text-sm text-slate-500 sm:px-8">
          Reads from <span className="text-slate-300">GitHub</span>,{" "}
          <span className="text-slate-300">Linear</span> and{" "}
          <span className="text-slate-300">Notion</span>. Read-only. AI proposes, people decide.
        </p>
      </div>

      {/* MANIFESTO */}
      <section className="manifesto relative h-[220svh]">
        <div className="sticky top-0 flex h-svh items-center">
          <div className="mx-auto w-full max-w-6xl px-6 sm:px-8">
            <span className="mb-8 block text-sm font-medium text-[#B8FF3C]">The problem</span>
            <p className="font-display text-[clamp(2.8rem,6.6vw,6rem)] leading-[1.02] tracking-[-0.01em]">
              {words.map((w, i) => {
                const a = 8 + (i / words.length) * 52;
                return (
                  <span
                    key={i}
                    className="word-fill text-[#F2EEE5]"
                    style={{ animationRange: `cover ${a}% cover ${a + 9}%` }}
                  >
                    {w}{" "}
                  </span>
                );
              })}
            </p>
          </div>
        </div>
      </section>

      {/* WHAT GOES WRONG */}
      <section id="exposure" className="relative scroll-mt-16 py-28">
        <div className="relative mx-auto max-w-7xl px-6 sm:px-8 lg:px-12">
          <SectionHeading
            theme="blue"
            align="left"
            eyebrow="What actually happens"
            title="Three things go wrong"
            accent="every time."
          />
          <ul className="glass mt-16 divide-y divide-white/10 px-4 md:px-6">
            {FAILURES.map((f) => (
              <li
                key={f.num}
                className="reveal group relative grid gap-6 overflow-hidden px-2 py-10 md:grid-cols-[9rem_minmax(0,1.15fr)_minmax(0,1fr)] md:items-center md:gap-10 md:px-6"
              >
                <span
                  aria-hidden
                  className="absolute inset-0 bg-gradient-to-r from-[#3B5BFF]/25 via-[#3B5BFF]/8 to-transparent opacity-0 transition-opacity duration-500 group-hover:opacity-100"
                />
                <span className="font-display display-outline relative text-[7rem] leading-[0.8] tracking-wider transition-all duration-500 group-hover:[-webkit-text-stroke-color:#B8FF3C]">
                  {f.num}
                </span>
                <div className="relative">
                  <span className="text-xs text-[#B8FF3C]">{f.tag}</span>
                  <h3 className="mt-3 text-2xl leading-snug font-semibold text-[#F2EEE5] sm:text-3xl">
                    {f.headline}
                  </h3>
                </div>
                <p className="relative text-[0.95rem] leading-relaxed text-slate-400 transition-colors group-hover:text-slate-200">
                  {f.desc}
                </p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* THE GAP */}
      <section id="gap" className="relative scroll-mt-16 py-28">
        <div className="relative mx-auto grid max-w-7xl gap-14 px-6 sm:px-8 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.3fr)] lg:px-12">
          <div className="lg:sticky lg:top-28 lg:self-start">
            <SectionHeading
              theme="blue"
              align="left"
              eyebrow="The gap"
              title="Your tools each hold a piece."
              accent="None answers this."
            />
            <blockquote className="reveal mt-10 border-l-2 border-[#B8FF3C] pl-6">
              <p className="font-display text-4xl leading-tight text-[#F2EEE5] italic sm:text-5xl">
                If Arjun is away for two weeks, what breaks, who should cover, and did the handover
                actually happen?
              </p>
              <p className="mt-5 text-sm leading-relaxed text-slate-400">
                Relay is the connection between those boundaries: one record of who is accountable
                for what, the evidence behind it, a forecast of what an absence breaks, and an
                audited transfer that ends with the new owner confirmed.
              </p>
            </blockquote>
          </div>

          <ul className="glass divide-y divide-white/10 px-7">
            {GAP.map((g) => (
              <li
                key={g.cat}
                className="reveal grid gap-3 py-7 sm:grid-cols-[11rem_minmax(0,1fr)] sm:gap-8"
              >
                <div>
                  <span className="text-lg font-semibold text-[#F2EEE5]">{g.cat}</span>
                </div>
                <div className="text-sm leading-relaxed">
                  <p className="text-slate-300">
                    <span className="text-xs text-lime-400">Owns </span>
                    {g.owns}
                  </p>
                  <p className="mt-2 text-slate-500">
                    <span className="text-xs text-[#FF6B7A]">Stops </span>
                    {g.stops}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* THE JOURNEY */}
      <section className="relative overflow-hidden py-28">
        <div className="relative mx-auto max-w-7xl px-6 sm:px-8 lg:px-12">
          <SectionHeading
            theme="blue"
            eyebrow="The Relay answer"
            title="One journey, from"
            accent="history to proof."
            description="The features are not separate tools. Each one hands off to the next, and every arrow is a link in the product."
          />
          <ol className="relative mt-20 grid gap-10 md:grid-cols-5 md:gap-5">
            <div
              aria-hidden
              className="absolute top-[22px] right-[10%] left-[10%] hidden h-px bg-gradient-to-r from-[#B8FF3C] via-[#FF6B7A] to-[#8FA8FF] opacity-40 md:block"
            />
            {JOURNEY.map((j, i) => (
              <li key={j.phase} className="reveal relative">
                <span
                  className="font-display relative z-10 grid h-11 w-11 place-items-center rounded-full border bg-[#04060F]/60 text-2xl backdrop-blur-md"
                  style={{
                    color: j.tone,
                    borderColor: j.tone,
                    boxShadow: `0 0 22px -4px ${j.tone}`,
                  }}
                >
                  {i + 1}
                </span>
                <h3 className="font-display mt-5 text-3xl text-[#F2EEE5]">{j.phase}</h3>
                <ul className="mt-3 space-y-2 text-sm text-slate-400">
                  {j.steps.map((s) => (
                    <li key={s} className="flex gap-2">
                      <span className="mt-2 h-px w-3 shrink-0" style={{ background: j.tone }} />
                      {s}
                    </li>
                  ))}
                </ul>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <BlueHalf />
    </>
  );
}

export { LandingFooter } from "@/components/landing/landing-blue";
