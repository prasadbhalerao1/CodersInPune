import { withAuth } from "@workos-inc/authkit-nextjs";
import type { Metadata } from "next";
import Link from "next/link";
import { connection } from "next/server";
import { Suspense } from "react";
import { ArrowRight } from "lucide-react";

import { HeroCanvasBackground } from "@/components/landing/hero-canvas-background";
import { Petals } from "@/components/landing/petals";
import { QuantumCapsule3D } from "@/components/landing/quantum-capsule-3d";
import { HeroReadout } from "@/components/landing/hero-readout";
import { RelayMark } from "@/components/brand";
import { ThemeToggle } from "@/components/theme-toggle";
import { HeroCrew } from "@/components/landing/figures/hero-crew";
import { Interlude } from "@/components/landing/figures/interlude";
import { Roamer } from "@/components/landing/figures/roamer";
import { HeroRelay } from "@/components/landing/figures/hero-relay";
import { BlueArt } from "@/components/landing/landing-blue";
import { LandingFooter, LandingSections } from "@/components/landing/landing-sections";
import { StickyHeader } from "@/components/landing/sticky-header";
import { REPO_URL, SITE_DESCRIPTION, SITE_URL } from "@/lib/site";

export const metadata: Metadata = {
  title: { absolute: "Relay: keep work moving when people move on" },
  description:
    "When lead engineers leave, the work shouldn't stall. Relay forecasts what an absence breaks and hands the work over with cited evidence.",
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

export default function HomePage() {
  return (
    <div className="landing-root bg-page text-strong selection:bg-lime selection:text-cta-fg relative min-h-svh overflow-x-clip">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: STRUCTURED_DATA }} />

      <Roamer />
      <Interlude />
      <BlueArt />

      {/* Floating header over the hero (no bar, no border, as in the reference) */}
      <StickyHeader>
        <div className="mx-auto grid h-16 max-w-7xl grid-cols-2 items-center px-6 sm:px-8 lg:grid-cols-[1fr_auto_1fr] lg:px-12">
          <Link href="/" className="group flex items-center gap-2.5 justify-self-start">
            <RelayMark className="h-8 w-8 drop-shadow-[0_0_10px_rgba(90,120,255,0.5)]" />
            <span className="text-strong font-sans text-[22px] font-medium tracking-tight">
              Relay
            </span>
          </Link>

          <nav
            aria-label="Sections"
            className="text-fg-soft glass hidden items-center gap-5 !rounded-full px-5 py-2.5 text-[13px] lg:flex xl:gap-8 xl:px-7"
          >
            <a href="#overview" className="hover:text-strong hidden transition-colors xl:inline">
              Overview
            </a>
            <a href="#exposure" className="hover:text-strong transition-colors">
              Problem
            </a>
            <a href="#product" className="hover:text-strong transition-colors">
              Product
            </a>
            <a href="#how" className="hover:text-strong transition-colors">
              How it works
            </a>
            <a href="#trust" className="hover:text-strong transition-colors">
              Trust
            </a>
            <a href="#try" className="hover:text-strong transition-colors">
              Try it
            </a>
          </nav>

          <div className="flex items-center gap-3 justify-self-end">
            <ThemeToggle hint />
            <Suspense fallback={<NavActionLink label="LAUNCH SANDBOX" short="SANDBOX" />}>
              <PrimaryNavAction />
            </Suspense>
          </div>
        </div>
      </StickyHeader>

      <main className="relative">
        {/* ==========================================================================
            HERO SECTION
            ========================================================================== */}
        <section
          id="overview"
          className="relative flex min-h-svh flex-col justify-between overflow-hidden"
        >
          <HeroCanvasBackground />
          <HeroCrew />

          {/* CONTINUITY outline: centred behind the capsule, running off the right edge */}
          <div
            aria-hidden
            className="pointer-events-none absolute top-[13%] right-[7%] z-[12] hidden select-none lg:block"
          >
            <span className="font-bebas hero-outline block text-[clamp(5rem,12vw,12rem)] leading-none tracking-[0.03em] whitespace-nowrap">
              CONTINUITY
            </span>
          </div>

          {/* Orchid behind the capsule: in front of the slash, behind the capsule */}
          <Petals
            variant="light"
            className="pointer-events-none absolute right-[-3%] bottom-[-4%] z-[6] hidden h-[94%] w-[68vw] max-w-[1150px] [mask-image:radial-gradient(closest-side,#000_64%,transparent_100%)] lg:block"
            petals={[
              { x: 480, y: 800, rot: -70, s: 1.2, o: 0.8, blur: true },
              { x: 600, y: 800, rot: -38, s: 1.45, o: 0.95 },
              { x: 760, y: 800, rot: -6, s: 1.7, o: 1 },
              { x: 920, y: 800, rot: 30, s: 1.5, o: 0.95 },
              { x: 1040, y: 800, rot: 62, s: 1.2, o: 0.8, blur: true },
            ]}
          />

          {/* Capsule: large, diagonal, overlapping the copy column (desktop) */}
          <div className="pointer-events-none absolute top-1/2 right-[5%] z-10 hidden w-[60vw] max-w-[1080px] -translate-y-[50%] lg:block">
            <QuantumCapsule3D />
          </div>

          {/* What-if readout (desktop): the same numbers as the simulator below */}
          <div className="pointer-events-none absolute inset-x-0 bottom-[25.8%] z-30 hidden lg:block">
            <div className="mx-auto flex max-w-7xl justify-end px-12">
              <div className="pointer-events-auto" data-fig="readout">
                <HeroReadout />
              </div>
            </div>
          </div>

          <div className="relative z-20 mx-auto flex w-full max-w-7xl flex-1 flex-col justify-center px-6 pt-28 pb-14 sm:px-8 lg:px-12">
            <div className="mx-auto max-w-[640px] text-center lg:mx-0 lg:text-left">
              <h1 className="hero-in flex flex-col items-center select-none lg:items-start">
                <span className="font-display text-ac text-[clamp(3.4rem,7.6vw,6.6rem)] leading-[0.9] tracking-[-0.02em] italic">
                  Pass the
                </span>
                <span className="font-display text-strong text-[clamp(2.8rem,6.4vw,5.6rem)] leading-[0.95] tracking-[-0.01em]">
                  accountability.
                </span>
              </h1>

              <p className="hero-in hero-in-2 scrim text-fg-soft mx-auto mt-6 max-w-[28rem] text-[1.1rem] leading-snug lg:mx-0">
                When lead engineers leave, the work shouldn&apos;t stall. Relay simulates an
                absence&apos;s blast radius and hands the work over with cited evidence.
              </p>

              <div className="hero-in hero-in-3 mt-9 flex flex-col items-center gap-4 lg:items-start">
                <Link
                  href="#simulator"
                  data-fig="cta"
                  className="group bg-cta text-cta-fg hover:bg-cta-hover inline-flex h-11 w-[15.5rem] items-center justify-center gap-2.5 rounded-full px-6 text-sm font-semibold transition-colors"
                >
                  <span className="bg-page/70 h-2 w-2 rounded-full" />
                  <span>INITIALIZE SIMULATOR</span>
                  <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
                </Link>
                <a
                  href="#how"
                  className="glass-clear text-fg-soft hover:text-strong inline-flex h-11 w-[15.5rem] items-center justify-center gap-2.5 !rounded-full px-6 text-sm font-medium transition-colors"
                >
                  <span>(▷) SYSTEM FILM</span>
                </a>
              </div>
            </div>

            {/* Capsule + card stacked under the copy on small screens */}
            <div className="relative mt-12 overflow-clip rounded-3xl bg-gradient-to-br from-[#3A58FF] via-[#1D32C2] to-[#08104A] px-3 pt-6 pb-5 lg:hidden">
              <Petals
                variant="light"
                className="pointer-events-none absolute inset-0 h-full w-full opacity-90"
                petals={[
                  { x: 480, y: 800, rot: -70, s: 1.2, o: 0.8, blur: true },
                  { x: 600, y: 800, rot: -38, s: 1.45, o: 0.95 },
                  { x: 760, y: 800, rot: -6, s: 1.7, o: 1 },
                  { x: 920, y: 800, rot: 30, s: 1.5, o: 0.95 },
                  { x: 1040, y: 800, rot: 62, s: 1.2, o: 0.8, blur: true },
                ]}
              />
              <QuantumCapsule3D />
              <div className="mt-2 flex justify-center">
                <HeroReadout />
              </div>
            </div>
          </div>

          {/* Bottom hairline bar */}
          <div className="border-line/[0.1] bg-page/80 relative z-20 w-full shrink-0 border-t py-2.5 backdrop-blur-md">
            <HeroRelay />
            <div className="text-fg-mute mx-auto flex max-w-7xl flex-wrap items-center justify-start gap-x-3 px-6 text-xs sm:px-8 lg:px-12">
              <span>Reads GitHub, Linear and Notion</span>
              <span aria-hidden>·</span>
              <span>Read-only</span>
              <span aria-hidden>·</span>
              <span>AI proposes, people decide</span>
            </div>
          </div>
        </section>

        <LandingSections />
      </main>

      <LandingFooter />
    </div>
  );
}

function NavActionLink({ label, short }: { label: string; short: string }) {
  return (
    <Link
      href="/workspaces"
      aria-label={label}
      className="group bg-cta text-cta-fg hover:bg-cta-hover inline-flex h-11 items-center gap-2 rounded-full px-5 text-xs font-bold tracking-wider whitespace-nowrap transition-colors"
    >
      {/* the full label from 640px; a phone header has room for one word */}
      <span className="sm:hidden">{short}</span>
      <span className="hidden sm:inline">{label}</span>
      <ArrowRight className="h-3 w-3 transition-transform group-hover:translate-x-0.5" />
    </Link>
  );
}

async function PrimaryNavAction() {
  await connection();
  const { user } = await withAuth();
  return user ? (
    <NavActionLink label="WORKSPACES" short="WORKSPACES" />
  ) : (
    <NavActionLink label="LAUNCH SANDBOX" short="SANDBOX" />
  );
}
