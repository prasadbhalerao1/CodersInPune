import { withAuth } from "@workos-inc/authkit-nextjs";
import type { Metadata } from "next";
import Link from "next/link";
import { connection } from "next/server";
import { Suspense } from "react";
import { ArrowRight, ChevronRight, Clock, Database, FileCheck, Lock } from "lucide-react";

import { Walkthrough } from "@/components/landing/walkthrough";
import { HeroSandbox } from "@/components/landing/hero-sandbox";
import { MemoryReplayPreview } from "@/components/landing/memory-replay-preview";
import { HeroCanvasBackground } from "@/components/landing/hero-canvas-background";
import { QuantumCapsule3D } from "@/components/landing/quantum-capsule-3d";
import { BlastRadiusCard } from "@/components/landing/blast-radius-card";
import { REPO_URL, SITE_DESCRIPTION, SITE_URL } from "@/lib/site";

export const metadata: Metadata = {
  title: "Relay — Sovereign Organisational Continuity",
  description:
    "When lead engineers leave, the work shouldn't stall. Relay simulates absence blast radii and transfers knowledge with zero-hallucination citations.",
};

const STRUCTURED_DATA = JSON.stringify({
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: "Relay",
  applicationCategory: "BusinessApplication",
  operatingSystem: "Web",
  url: SITE_URL,
  description: SITE_DESCRIPTION,
  sameAs: [REPO_URL],
  featureList: [
    "Responsibility ownership with primary owners, co-owners and backups",
    "Continuity risks and key-person exposure from explainable rules",
    "Project Memory Replay: cited history of a responsibility from GitHub, Linear and Notion",
    "What If? simulator: deterministic, read-only absence impact and cover candidates",
    "AI Handover Copilot: evidence-backed handover briefs, coverage, versions and cited Q&A",
    "Audited handover cases with approval, acknowledgement and verification",
  ],
}).replace(/</g, "\\u003c");

const VULNERABILITIES = [
  {
    num: "01",
    tag: "SINGLE-POINT EXPOSURE",
    headline: "Critical systems quietly depend on one person.",
    desc: "Until the day they give 2 weeks notice or take leave, and your production deployment mesh becomes a black box with zero active backups.",
  },
  {
    num: "02",
    tag: "CONTEXT FRAGMENTATION",
    headline: "Decisions decay in PRs, tickets, and unread docs.",
    desc: "Why an architectural compromise was made is lost in closed GitHub pull requests, archived Slack threads, and outdated Notion wikis nobody can find.",
  },
  {
    num: "03",
    tag: "SPECULATIVE HANDOVERS",
    headline: "Ownership moves via hasty 30-minute meetings.",
    desc: "Unstructured Slack notes and generic AI summaries that invent facts when context is missing, leaving successors stranded without audited runbooks.",
  },
];

const PROOF_CARDS = [
  {
    icon: Database,
    code: "POSTGRESQL 17 // FORCED RLS",
    title: "Kernel-Level Tenant Isolation",
    desc: "Row Level Security is forced at the database layer. The application role and background workers cannot read or write across tenants, even through a bug in application code.",
    spec: "EVERY TENANT TABLE",
  },
  {
    icon: Clock,
    code: "TEMPORAL GiST CONSTRAINTS",
    title: "Double-Ownership is Mathematically Impossible",
    desc: "Database-level exclusion constraints prevent overlapping primary ownership windows. Continuity history is valid-time tracked with microsecond accuracy.",
    spec: "ZERO RACE CONDITIONS",
  },
  {
    icon: FileCheck,
    code: "GROUNDED CITATION GATE",
    title: "Strict Zero-Hallucination Mandate",
    desc: "The Copilot strictly refuses to speculate. If an assertion cannot be cited with an exact GitHub PR, Linear issue, or Notion page receipt, it is dropped from the brief.",
    spec: "100% AUDITED CLAIMS",
  },
];

export default function HomePage() {
  return (
    <div className="relative min-h-svh overflow-x-hidden bg-[#02050C] text-[#F5F5F7] selection:bg-[#D2FF00] selection:text-[#02050C]">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: STRUCTURED_DATA }} />

      {/* Floating header over the hero (no bar, no border, as in the reference) */}
      <header className="absolute inset-x-0 top-0 z-50">
        <div className="mx-auto flex h-16 max-w-[1360px] items-center justify-between px-6 sm:px-8 lg:px-12">
          <Link href="/" className="group flex items-center gap-2.5">
            <svg
              aria-hidden
              viewBox="0 0 24 24"
              className="h-7 w-7 drop-shadow-[0_0_6px_rgba(215,38,61,0.6)]"
            >
              <path
                d="M6.5 6.5c3.5-4 11.5-3.5 11.5 2.5S8 12.5 8 16.5c0 4 6.5 4.5 10 0.5"
                fill="none"
                stroke="#D7263D"
                strokeWidth="3.2"
                strokeLinecap="round"
              />
            </svg>
            <span className="font-sans text-[22px] font-medium tracking-tight text-white">
              Relay
            </span>
          </Link>

          <nav
            aria-label="Sections"
            className="hidden items-center gap-9 text-[13px] text-zinc-400 md:flex"
          >
            <a href="#overview" className="transition-colors hover:text-white">
              Overview
            </a>
            <a href="#product" className="transition-colors hover:text-white">
              Product
            </a>
            <a href="#how" className="transition-colors hover:text-white">
              Solutions
            </a>
            <a href="#trust" className="transition-colors hover:text-white">
              Pricing
            </a>
            <a href="#exposure" className="transition-colors hover:text-white">
              Customers
            </a>
            <a href="#simulator" className="transition-colors hover:text-white">
              Relay
            </a>
          </nav>

          <div>
            <Suspense fallback={<NavActionLink label="LAUNCH SANDBOX" />}>
              <PrimaryNavAction />
            </Suspense>
          </div>
        </div>
      </header>

      <main className="relative">
        {/* ==========================================================================
            HERO SECTION
            ========================================================================== */}
        <section
          id="overview"
          className="relative flex min-h-svh flex-col justify-between overflow-hidden bg-[#090D18]"
        >
          <HeroCanvasBackground />

          {/* CONTINUITY outline: centred behind the capsule, running off the right edge */}
          <div
            aria-hidden
            className="pointer-events-none absolute top-[13%] right-[7%] z-[5] hidden select-none lg:block"
          >
            <span className="font-bebas display-outline block text-[clamp(5rem,12vw,12rem)] leading-none tracking-[0.03em] whitespace-nowrap text-transparent">
              CONTINUITY
            </span>
          </div>

          {/* Capsule: large, diagonal, overlapping the copy column (desktop) */}
          <div className="pointer-events-none absolute top-1/2 right-[5%] z-10 hidden w-[60vw] max-w-[1080px] -translate-y-[50%] lg:block">
            <QuantumCapsule3D />
          </div>

          {/* Telemetry card (desktop) */}
          <div className="absolute right-[11%] bottom-[13%] z-30 hidden lg:block">
            <BlastRadiusCard />
          </div>

          <div className="relative z-20 mx-auto flex w-full max-w-[1360px] flex-1 flex-col justify-center px-6 pt-28 pb-14 sm:px-8 lg:px-12">
            <div className="mx-auto max-w-[640px] text-center lg:mx-0 lg:text-left">
              <h1 className="flex flex-col items-center select-none lg:items-start">
                <span className="font-script text-[clamp(2.4rem,5.4vw,5rem)] leading-none text-[#F1EDE6] drop-shadow-[0_2px_12px_rgba(0,0,0,0.8)]">
                  Pass the
                </span>
                <span className="font-bebas -mt-1 text-[clamp(2.8rem,8.6vw,8rem)] leading-[0.86] tracking-[-0.01em] text-[#F1EDE6] uppercase drop-shadow-[0_4px_20px_rgba(0,0,0,0.9)]">
                  ACCOUNTABILITY.
                </span>
              </h1>

              <p className="mx-auto mt-6 max-w-[28rem] text-[1.1rem] leading-snug text-zinc-300 lg:mx-0">
                When lead engineers leave, the work shouldn&apos;t stall. Relay simulates absence
                blast radii and transfers knowledge with zero-hallucination citations.
              </p>

              <div className="mt-9 flex flex-col items-center gap-4 lg:items-start">
                <Link
                  href="#simulator"
                  className="luxury-btn group !h-11 !px-6 !text-[0.72rem] !tracking-[0.1em]"
                >
                  <span className="h-2.5 w-2.5 rounded-full bg-[#C4FF00] shadow-[0_0_12px_2px_#C4FF00]" />
                  <span>INITIALIZE SIMULATOR</span>
                  <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-1" />
                </Link>
                <a
                  href="#how"
                  className="inline-flex h-11 items-center gap-2.5 rounded-full border border-white/25 bg-white/[0.03] px-6 font-mono text-[0.72rem] font-medium tracking-[0.1em] text-zinc-200 uppercase backdrop-blur-md transition-all hover:border-white/50 hover:text-white"
                >
                  <span>(▷) SYSTEM FILM</span>
                </a>
              </div>
            </div>

            {/* Capsule + card stacked under the copy on small screens */}
            <div className="relative mt-12 lg:hidden">
              <QuantumCapsule3D />
              <div className="mt-4 flex justify-center">
                <BlastRadiusCard />
              </div>
            </div>
          </div>

          {/* Bottom hairline bar */}
          <div className="relative z-20 w-full shrink-0 border-t border-white/[0.08] px-6 py-2.5 sm:px-8 lg:px-12">
            <div className="mx-auto flex max-w-[1360px] items-center justify-end gap-x-3 font-mono text-[9px] tracking-[0.12em] text-zinc-500 uppercase">
              <span>BOTTOM HAIRLINE</span>
              <span>MICRO-TELEMETRY STATS</span>
              <span>|</span>
              <span>BK: 3.000</span>
              <span>MUR CALAE</span>
              <span>4 0.000</span>
            </div>
          </div>
        </section>

        {/* ==========================================================================
            SECTION 2: ZERO-LOGIN INTERACTIVE SIMULATOR (WAR ROOM STRESS-TEST)
            ========================================================================== */}
        <section
          id="simulator"
          className="scroll-mt-16 border-b border-white/[0.08] bg-[#06070B] py-24"
        >
          <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
            <div className="mx-auto mb-10 max-w-xl text-center">
              <span className="block font-mono text-xs tracking-widest text-[#C4FF00] uppercase">
                OPERATIONAL STRESS-TEST ENGINE
              </span>
              <h2 className="font-syne mt-2 text-3xl font-extrabold text-white sm:text-5xl">
                SIMULATE DEPARTURE BLAST RADIUS.
              </h2>
              <p className="mt-3 text-sm text-zinc-400">
                Experience real-time absence impact, single-point vulnerabilities, and algorithmic
                candidate load balancing with zero login.
              </p>
            </div>

            <div className="mx-auto max-w-2xl">
              <HeroSandbox />
            </div>
          </div>
        </section>

        {/* ==========================================================================
            SECTION 3: THE EXPOSURE (THE 3 CRITICAL CONTINUITY VULNERABILITIES)
            ========================================================================== */}
        <section
          id="exposure"
          className="scroll-mt-16 border-b border-white/[0.08] bg-[#080B10] py-20"
        >
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="flex flex-col justify-between gap-4 border-b border-white/[0.08] pb-8 sm:flex-row sm:items-end">
              <div>
                <span className="block font-mono text-xs tracking-widest text-[#D2FF00] uppercase">
                  01 // ROOT FAILURE MODES
                </span>
                <h2 className="font-syne mt-2 text-3xl font-extrabold text-white sm:text-4xl">
                  WHERE REVENUE & MOMENTUM DIE.
                </h2>
              </div>
              <p className="max-w-md text-xs text-zinc-400 sm:text-sm">
                Organisations don&apos;t fail from lack of talent; they fail from silent handovers
                and lost leverage.
              </p>
            </div>

            <div className="mt-12 grid grid-cols-1 gap-6 md:grid-cols-3">
              {VULNERABILITIES.map((v) => (
                <div
                  key={v.num}
                  className="group relative flex flex-col justify-between rounded-2xl border border-white/10 bg-[#0E1118]/80 p-6 backdrop-blur-md transition-all hover:border-[#D2FF00]/40 hover:bg-[#121622]"
                >
                  <div>
                    <div className="flex items-center justify-between">
                      <span className="font-syne text-3xl font-black text-zinc-700 transition-colors group-hover:text-[#D2FF00]">
                        {v.num}
                      </span>
                      <span className="rounded border border-white/10 px-2 py-0.5 font-mono text-[9px] tracking-wider text-zinc-500 uppercase">
                        {v.tag}
                      </span>
                    </div>
                    <h3 className="mt-4 text-lg leading-snug font-semibold text-white">
                      {v.headline}
                    </h3>
                    <p className="mt-2 text-xs leading-relaxed text-zinc-400">{v.desc}</p>
                  </div>
                  <div className="mt-6 flex items-center gap-1 font-mono text-[10px] text-zinc-500 group-hover:text-zinc-300">
                    <span>MITIGATION: AUTOMATED RLS AUDIT</span>
                    <ChevronRight className="h-3 w-3" />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ==========================================================================
            SECTION 4: THE 3 UNBREAKABLE PILLARS (THE CONTINUITY ENGINE)
            ========================================================================== */}
        <section id="product" className="border-b border-white/[0.08] bg-[#06070B] py-24">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="mx-auto max-w-2xl text-center">
              <span className="block font-mono text-xs tracking-widest text-[#00F5A0] uppercase">
                THE CONTINUITY ENGINE
              </span>
              <h2 className="font-syne mt-2 text-3xl font-extrabold text-white sm:text-5xl">
                THREE PILLARS. ZERO AMNESIA.
              </h2>
              <p className="mt-3 text-sm text-zinc-400">
                Forecast exposure before notice is given. Reconstruct the unwritten decisions.
                Execute audited transfers.
              </p>
            </div>

            <div className="mt-16 grid grid-cols-1 gap-8 lg:grid-cols-3">
              {/* Pillar 01: FORECAST */}
              <div className="flex flex-col justify-between rounded-2xl border border-white/10 bg-[#0B0E16] p-6 shadow-xl">
                <div>
                  <div className="flex items-center justify-between border-b border-white/[0.08] pb-4">
                    <span className="font-mono text-xs font-bold text-[#FF334B]">
                      PILLAR 01 // FORECAST
                    </span>
                    <span className="jewel-crimson" />
                  </div>
                  <h3 className="font-syne mt-5 text-2xl font-bold text-white">
                    Blast Radius <span className="text-[#FF334B]">Stress-Test</span>
                  </h3>
                  <p className="mt-2 text-xs leading-relaxed text-zinc-400">
                    Simulate absences before they happen. Relay automatically calculates
                    single-point vulnerabilities, successor candidate capacities, and overload
                    penalties across your entire team topology.
                  </p>

                  <div className="mt-6 rounded-xl border border-white/10 bg-black/50 p-3.5 font-mono text-[11px]">
                    <div className="flex justify-between text-zinc-400">
                      <span>KEY PERSON ABSENT:</span>
                      <span className="font-bold text-rose-400">14 DAYS</span>
                    </div>
                    <div className="mt-2 flex justify-between text-zinc-400">
                      <span>UNBACKED RESPONSIBILITIES:</span>
                      <span className="font-bold text-rose-400">3 SERVICES</span>
                    </div>
                    <div className="mt-2 flex justify-between text-zinc-400">
                      <span>SUGGESTED STEWARD:</span>
                      <span className="font-bold text-emerald-400">DEV PATEL (88%)</span>
                    </div>
                  </div>
                </div>

                <div className="mt-6 border-t border-white/[0.08] pt-4">
                  <span className="block font-mono text-[10px] tracking-wider text-zinc-500 uppercase">
                    GOAL: ELIMINATE SUDDEN SYSTEM PARALYSIS
                  </span>
                </div>
              </div>

              {/* Pillar 02: RECONSTRUCT */}
              <div
                id="memory"
                className="flex scroll-mt-24 flex-col justify-between rounded-2xl border border-white/10 bg-[#0B0E16] p-6 shadow-xl"
              >
                <div>
                  <div className="flex items-center justify-between border-b border-white/[0.08] pb-4">
                    <span className="font-mono text-xs font-bold text-[#D2FF00]">
                      PILLAR 02 // RECONSTRUCT
                    </span>
                    <span className="jewel-chartreuse" />
                  </div>
                  <h3 className="font-syne mt-5 text-2xl font-bold text-white">
                    Project Memory <span className="text-[#D2FF00]">Replay</span>
                  </h3>
                  <p className="mt-2 text-xs leading-relaxed text-zinc-400">
                    A year of closed PRs, Linear tickets, and Notion architectural docs synthesized
                    into auditable, chronological chapters. Every claim is verified with an exact
                    source citation.
                  </p>

                  <div className="mt-6">
                    <MemoryReplayPreview />
                  </div>
                </div>

                <div className="mt-6 border-t border-white/[0.08] pt-4">
                  <span className="block font-mono text-[10px] tracking-wider text-zinc-500 uppercase">
                    GOAL: RESCUE DECISIONS FROM STALE WIKIS
                  </span>
                </div>
              </div>

              {/* Pillar 03: TRANSFER */}
              <div className="flex flex-col justify-between rounded-2xl border border-white/10 bg-[#0B0E16] p-6 shadow-xl">
                <div>
                  <div className="flex items-center justify-between border-b border-white/[0.08] pb-4">
                    <span className="font-mono text-xs font-bold text-[#00F5A0]">
                      PILLAR 03 // TRANSFER
                    </span>
                    <span className="jewel-emerald" />
                  </div>
                  <h3 className="font-syne mt-5 text-2xl font-bold text-white">
                    Audited <span className="text-[#00F5A0]">Handover Capsules</span>
                  </h3>
                  <p className="mt-2 text-xs leading-relaxed text-zinc-400">
                    Role-specific handover dossiers, verified by dual-key separation of duties.
                    Successors inherit curated runbooks, access inventories, and a grounded AI
                    Copilot that strictly refuses to guess.
                  </p>

                  <div className="mt-6 rounded-xl border border-emerald-500/20 bg-emerald-950/10 p-3.5">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-[10px] font-semibold text-emerald-400 uppercase">
                        CLASSIFIED HANDOVER DOSSIER
                      </span>
                      <span className="rounded bg-emerald-500/20 px-1.5 py-0.5 font-mono text-[9px] text-emerald-300">
                        VERIFIED
                      </span>
                    </div>
                    <p className="mt-2 text-xs text-zinc-300">
                      &ldquo;Production Deployments transition from Arjun to Dev approved by
                      Engineering VP. 4 runbooks acknowledged.&rdquo;
                    </p>
                    <div className="mt-3 flex items-center justify-between border-t border-white/10 pt-2 font-mono text-[9px] text-zinc-400">
                      <span>APPROVAL: DUAL-KEY SEAL</span>
                      <span>STATUS: SEALED</span>
                    </div>
                  </div>
                </div>

                <div className="mt-6 border-t border-white/[0.08] pt-4">
                  <span className="block font-mono text-[10px] tracking-wider text-zinc-500 uppercase">
                    GOAL: FORMAL, UNFORGETTABLE ACCOUNTABILITY
                  </span>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ==========================================================================
            SECTION 5: SYSTEM CHOREOGRAPHY WALKTHROUGH
            ========================================================================== */}
        <section id="how" className="scroll-mt-16 border-b border-white/[0.08] bg-[#080B10] py-24">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="flex flex-col justify-between gap-6 border-b border-white/[0.08] pb-8 md:flex-row md:items-end">
              <div>
                <span className="block font-mono text-xs tracking-widest text-[#D2FF00] uppercase">
                  SYSTEM CHOREOGRAPHY
                </span>
                <h2 className="font-syne mt-2 text-3xl font-extrabold text-white sm:text-5xl">
                  THE CONTINUITY LOOP IN ACTION.
                </h2>
              </div>
              <p className="max-w-md text-xs text-zinc-400 sm:text-sm">
                From departure signal to verified successor sign-off. Click any phase or let the
                timeline advance.
              </p>
            </div>

            <div className="mt-12 rounded-2xl border border-white/10 bg-[#0E1118]/90 p-6 shadow-2xl backdrop-blur-xl">
              <Walkthrough />
            </div>
          </div>
        </section>

        {/* ==========================================================================
            SECTION 6: CRAFTSMANSHIP & SOVEREIGN TRUST
            ========================================================================== */}
        <section
          id="trust"
          className="scroll-mt-16 border-b border-white/[0.08] bg-[#06070B] py-24"
        >
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <div className="mx-auto max-w-2xl text-center">
              <span className="block font-mono text-xs tracking-widest text-emerald-400 uppercase">
                SOVEREIGN FOUNDATION
              </span>
              <h2 className="font-syne mt-2 text-3xl font-extrabold text-white sm:text-5xl">
                BUILT LIKE A SWISS TIMEPIECE.
              </h2>
              <p className="mt-3 text-sm text-zinc-400">
                Continuity data is sensitive. Relay is architected so the safe path is the only
                path.
              </p>
            </div>

            <div className="mt-16 grid grid-cols-1 gap-6 md:grid-cols-3">
              {PROOF_CARDS.map((p, idx) => {
                const Icon = p.icon;
                return (
                  <div
                    key={idx}
                    className="relative flex flex-col justify-between rounded-2xl border border-white/10 bg-[#0E1118] p-6 shadow-lg transition-all hover:border-white/20"
                  >
                    <div>
                      <div className="flex items-center justify-between">
                        <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] text-[#D2FF00]">
                          <Icon className="h-5 w-5" />
                        </div>
                        <span className="rounded border border-emerald-500/20 bg-emerald-500/10 px-2 py-0.5 font-mono text-[9px] tracking-wider text-emerald-400">
                          {p.spec}
                        </span>
                      </div>

                      <span className="mt-5 block font-mono text-[10px] tracking-wider text-zinc-500 uppercase">
                        {p.code}
                      </span>
                      <h3 className="mt-1 text-lg font-semibold text-white">{p.title}</h3>
                      <p className="mt-2 text-xs leading-relaxed text-zinc-400">{p.desc}</p>
                    </div>

                    <div className="mt-6 flex items-center gap-1 border-t border-white/[0.06] pt-4 font-mono text-[9px] text-zinc-500">
                      <Lock className="h-3 w-3 text-emerald-400" />
                      <span>CRYPTOGRAPHICALLY ENFORCED TENANT ISOLATION</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {/* ==========================================================================
            SECTION 7: GRAND FINALE EXECUTIVE CTA
            ========================================================================== */}
        <section className="relative overflow-hidden bg-gradient-to-b from-[#080B10] to-[#02050C] py-28">
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 bg-radial from-[#7E1520]/25 via-transparent to-transparent opacity-60 blur-3xl"
          />

          <div className="relative mx-auto max-w-5xl px-4 text-center sm:px-6 lg:px-8">
            <span className="block font-mono text-xs tracking-widest text-[#C4FF00] uppercase">
              IMMEDIATE ACCESS
            </span>
            <h2 className="font-bebas mt-4 text-5xl leading-none tracking-tight text-white uppercase sm:text-7xl lg:text-8xl">
              PASS THE <br />
              <span className="text-[#C4FF00]">ACCOUNTABILITY.</span>
            </h2>
            <p className="mx-auto mt-6 max-w-xl text-sm leading-relaxed text-zinc-400 sm:text-base">
              Experience the sample workspace &ldquo;Northwind Labs&rdquo; instantly with zero
              setup. Inspect live blast radii, review memory replay chapters, and execute verified
              handovers.
            </p>

            <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
              <Link href="/workspaces" className="luxury-btn group !h-14 !px-10 !text-sm">
                <span className="h-2.5 w-2.5 rounded-full bg-[#C4FF00] shadow-[0_0_12px_2px_#C4FF00]" />
                <span>TAKE COMMAND // INSTANT ACCESS</span>
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
              </Link>
            </div>

            <p className="mt-6 font-mono text-[10px] tracking-widest text-zinc-500 uppercase">
              READ-ONLY INTEGRATIONS · FORCED POSTGRES RLS · AUDIT RECORD PRESERVED
            </p>
          </div>
        </section>
      </main>

      {/* Global Executive Footer */}
      <footer className="border-t border-white/[0.08] bg-[#02050C] py-8">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 px-4 font-mono text-xs text-zinc-500 sm:flex-row sm:px-6 lg:px-8">
          <div className="flex items-center gap-3">
            <div className="h-2 w-2 rounded-full bg-[#7E1520]" />
            <span className="font-bold tracking-wider text-white">RELAY</span>
            <span className="text-zinc-600">·</span>
            <span>SOVEREIGN CONTINUITY</span>
          </div>

          <div className="flex items-center gap-6 text-[11px]">
            <a href="#overview" className="transition-colors hover:text-zinc-300">
              OVERVIEW
            </a>
            <a href="#simulator" className="transition-colors hover:text-zinc-300">
              STRESS-TEST
            </a>
            <a href="#memory" className="transition-colors hover:text-zinc-300">
              TRUE MEMORY
            </a>
            <a href="#trust" className="transition-colors hover:text-zinc-300">
              TRUST
            </a>
          </div>

          <div className="text-[10px] text-zinc-600">
            © 2026 RELAY SYSTEMS. ALL RIGHTS RESERVED.
          </div>
        </div>
      </footer>
    </div>
  );
}

function NavActionLink({ label }: { label: string }) {
  return (
    <Link
      href="/workspaces"
      className="luxury-btn group !h-9 border-t-white/30 border-b-black/60 !bg-[#161A23]/80 !px-5 !text-[11px] shadow-[0_4px_16px_rgba(0,0,0,0.6)]"
    >
      <span className="h-2 w-2 rounded-full bg-[#C4FF00] shadow-[0_0_8px_#C4FF00]" />
      <span className="font-semibold tracking-wider text-white">{label}</span>
      <ArrowRight className="h-3 w-3 text-white transition-transform group-hover:translate-x-0.5" />
    </Link>
  );
}

async function PrimaryNavAction() {
  await connection();
  const { user } = await withAuth();
  return <NavActionLink label={user ? "WORKSPACES" : "LAUNCH SANDBOX"} />;
}
