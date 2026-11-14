import { BlueHalf } from "@/components/landing/landing-blue";
import { CardRider } from "@/components/landing/figures/card-rider";
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
  {
    cat: "Relay",
    owns: "Who is accountable for what, with the evidence behind it",
    stops:
      "Forecasts what an absence breaks, hands the work over with citations, then checks it took hold.",
    answer: true,
  },
];

const JOURNEY = [
  {
    phase: "Understand",
    tone: "var(--ac)",
    steps: ["Memory Replay: how the work got here"],
  },
  {
    phase: "Forecast",
    tone: "var(--peri)",
    steps: ["What If? absence simulation", "Cover candidates and overload"],
  },
  {
    phase: "Decide",
    tone: "var(--ac)",
    steps: ["Pick a successor", "Open a pre-filled handover case"],
  },
  {
    phase: "Transfer",
    tone: "var(--peri)",
    steps: [
      "Handover Brief and interview",
      "Approve a version",
      "Recipient acknowledges",
      "Execute",
    ],
  },
  {
    phase: "Prove",
    tone: "var(--ac)",
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
      {/* MANIFESTO */}
      <section className="manifesto relative">
        <div className="flex min-h-svh items-center">
          <div className="mx-auto w-full max-w-7xl px-6 sm:px-8 lg:px-12">
            <span className="text-ac mb-8 block text-sm font-medium">The problem</span>
            <p className="scrim font-display text-[clamp(2.8rem,6.6vw,6rem)] leading-[1.02] tracking-[-0.01em]">
              {words.map((w, i) => {
                // One screen tall: arriving with the section at the top is cover 50%, so the last word
                // finishes exactly on arrival and the fill plays while the section slides in.
                const a = 12 + (i / words.length) * 30;
                return (
                  <span
                    key={i}
                    className="word-fill text-strong"
                    style={{ animationRange: `cover ${a}% cover ${a + 8}%` }}
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
      <section id="exposure" className="relative scroll-mt-12 py-20 md:mt-14 md:py-24">
        <div className="relative mx-auto max-w-7xl px-6 sm:px-8 lg:px-12">
          <SectionHeading
            theme="blue"
            align="left"
            eyebrow="What actually happens"
            title="Three things go wrong"
            accent="every time."
          />
          <ul className="glass divide-line/10 mt-12 divide-y px-4 py-2 md:mt-14 md:px-6">
            {FAILURES.map((f) => (
              <li
                key={f.num}
                className="reveal relative grid gap-6 overflow-clip rounded-xl px-2 py-10 md:grid-cols-[9rem_minmax(0,1.15fr)_minmax(0,1fr)] md:items-center md:gap-10 md:px-6"
              >
                <span
                  aria-hidden
                  className="lit-bg absolute inset-0 rounded-xl bg-gradient-to-r from-[#3B5BFF]/22 via-[#3B5BFF]/8 to-transparent"
                />
                <span className="lit-stroke font-display display-outline relative text-[7rem] leading-[0.8] tracking-wider">
                  {f.num}
                </span>
                <div className="relative">
                  <span className="text-ac text-xs">{f.tag}</span>
                  <h3 className="text-strong mt-3 text-2xl leading-snug font-semibold sm:text-3xl">
                    {f.headline}
                  </h3>
                </div>
                <p className="lit-text relative text-[0.95rem] leading-relaxed">{f.desc}</p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* THE GAP */}
      <section id="gap" className="relative scroll-mt-12 py-20 md:mt-14 md:py-24">
        <div className="relative mx-auto grid max-w-7xl gap-14 px-6 sm:px-8 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.3fr)] lg:px-12">
          <div className="lg:sticky lg:top-28 lg:self-start">
            <SectionHeading
              theme="blue"
              align="left"
              compact
              eyebrow="The gap"
              title="Your tools each hold a piece."
              accent="None answers this."
            />
            <blockquote className="reveal scrim border-ac mt-10 border-l-2 pl-6">
              <p className="font-display text-strong text-4xl leading-tight italic sm:text-5xl">
                If Arjun is away for two weeks, what breaks, who should cover, and did the handover
                actually happen?
              </p>
              <p className="text-fg-mute mt-5 text-sm leading-relaxed">
                Relay is the connection between those boundaries: one record of who is accountable
                for what, the evidence behind it, a forecast of what an absence breaks, and an
                audited transfer that ends with the new owner confirmed.
              </p>
            </blockquote>
          </div>

          <div className="relative lg:self-start">
            <CardRider />
            <ul className="glass divide-line/10 divide-y px-7">
              {GAP.map((g) => (
                <li
                  key={g.cat}
                  className="reveal grid gap-3 py-7 sm:grid-cols-[11rem_minmax(0,1fr)] sm:gap-8"
                >
                  <div>
                    <span
                      className={
                        g.answer
                          ? "text-ac text-lg font-semibold"
                          : "text-strong text-lg font-semibold"
                      }
                    >
                      {g.cat}
                    </span>
                  </div>
                  <div className="text-sm leading-relaxed">
                    <p className="text-fg-soft">
                      <span className="text-ac text-xs">Owns </span>
                      {g.owns}
                    </p>
                    <p className="text-fg-mute mt-2">
                      <span
                        className={
                          g.answer ? "text-ac text-xs font-semibold" : "text-coral text-xs"
                        }
                      >
                        {g.answer ? "Closes the gap " : "Stops "}
                      </span>
                      {g.stops}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* THE JOURNEY */}
      <section className="relative py-20 md:py-24">
        <div className="relative mx-auto max-w-7xl px-6 sm:px-8 lg:px-12">
          <div className="flex flex-col justify-between gap-6 md:flex-row md:items-end">
            <SectionHeading
              theme="blue"
              align="left"
              eyebrow="The Relay answer"
              title="One journey, from"
              accent="history to proof."
            />
            <p className="reveal scrim text-fg-mute max-w-sm text-sm leading-relaxed">
              The features are not separate tools. Each one hands off to the next, and every arrow
              is a link in the product.
            </p>
          </div>
          <div className="glass relative mt-12 p-6 md:mt-14 md:p-8">
            <div
              aria-hidden
              className="from-ac via-peri to-ac absolute top-[54px] right-[12%] left-[12%] hidden h-px bg-gradient-to-r opacity-40 md:block"
            />
            <ol className="relative grid gap-10 md:grid-cols-5 md:gap-5">
              {JOURNEY.map((j, i) => (
                <li key={j.phase} className="reveal relative">
                  <span
                    className="font-display bg-page/60 relative z-10 grid h-11 w-11 place-items-center rounded-full border text-2xl backdrop-blur-md"
                    style={{
                      color: j.tone,
                      borderColor: j.tone,
                      boxShadow: `0 0 22px -4px ${j.tone}`,
                    }}
                  >
                    {i + 1}
                  </span>
                  <h3 className="font-display text-strong mt-5 text-3xl">{j.phase}</h3>
                  <ul className="text-fg-mute mt-3 space-y-2 text-sm">
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
        </div>
      </section>

      <BlueHalf />
    </>
  );
}

export { LandingFooter } from "@/components/landing/landing-blue";
