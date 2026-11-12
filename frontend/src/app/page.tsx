import { withAuth } from "@workos-inc/authkit-nextjs";
import type { Metadata } from "next";
import Link from "next/link";
import { connection } from "next/server";
import { Suspense } from "react";
import { ArrowRight } from "lucide-react";

import { HeroCanvasBackground } from "@/components/landing/hero-canvas-background";
import { QuantumCapsule3D } from "@/components/landing/quantum-capsule-3d";
import { BlastRadiusCard } from "@/components/landing/blast-radius-card";
import { RelayMark } from "@/components/brand";
import { BlueArt } from "@/components/landing/landing-blue";
import { LandingFooter, LandingSections } from "@/components/landing/landing-sections";
import { StickyHeader } from "@/components/landing/sticky-header";
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

export default function HomePage() {
  return (
    <div className="relative min-h-svh overflow-x-clip bg-[#04060F] text-[#F2EEE5] selection:bg-[#B8FF3C] selection:text-[#04060F]">
      <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: STRUCTURED_DATA }} />

      <BlueArt />

      {/* Floating header over the hero (no bar, no border, as in the reference) */}
      <StickyHeader>
        <div className="mx-auto flex h-16 max-w-[1360px] items-center justify-between px-6 sm:px-8 lg:px-12">
          <Link href="/" className="group flex items-center gap-2.5">
            <RelayMark className="h-8 w-8 drop-shadow-[0_0_10px_rgba(90,120,255,0.5)]" />
            <span className="font-sans text-[22px] font-medium tracking-tight text-white">
              Relay
            </span>
          </Link>

          <nav
            aria-label="Sections"
            className="hidden items-center gap-9 text-[13px] text-slate-300 md:flex"
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
              <h1 className="hero-in flex flex-col items-center select-none lg:items-start">
                <span className="font-display text-[clamp(3.4rem,7.6vw,6.6rem)] leading-[0.9] tracking-[-0.02em] text-[#B8FF3C] italic">
                  Pass the
                </span>
                <span className="font-display text-[clamp(2.8rem,6.4vw,5.6rem)] leading-[0.95] tracking-[-0.01em] text-[#F2EEE5]">
                  accountability.
                </span>
              </h1>

              <p className="hero-in hero-in-2 mx-auto mt-6 max-w-[28rem] text-[1.1rem] leading-snug text-slate-300 lg:mx-0">
                When lead engineers leave, the work shouldn&apos;t stall. Relay simulates absence
                blast radii and transfers knowledge with zero-hallucination citations.
              </p>

              <div className="hero-in hero-in-3 mt-9 flex flex-col items-center gap-4 lg:items-start">
                <Link
                  href="#simulator"
                  className="group inline-flex h-11 items-center gap-2.5 rounded-full bg-[#B8FF3C] px-6 text-sm font-semibold text-[#04060F] transition-colors hover:bg-[#caff6a]"
                >
                  <span className="h-2 w-2 rounded-full bg-[#04060F]/70" />
                  <span>INITIALIZE SIMULATOR</span>
                  <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
                </Link>
                <a
                  href="#how"
                  className="glass-clear inline-flex h-11 items-center gap-2.5 !rounded-full px-6 text-sm font-medium text-slate-100 transition-colors hover:text-white"
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
          <div className="relative z-20 w-full shrink-0 border-t border-white/[0.1] px-6 py-2.5 backdrop-blur-sm sm:px-8 lg:px-12">
            <div className="mx-auto flex max-w-[1360px] items-center justify-end gap-x-3 font-mono text-[9px] tracking-[0.12em] text-slate-400 uppercase">
              <span>BOTTOM HAIRLINE</span>
              <span>MICRO-TELEMETRY STATS</span>
              <span>|</span>
              <span>BK: 3.000</span>
              <span>MUR CALAE</span>
              <span>4 0.000</span>
            </div>
          </div>
        </section>

        <LandingSections />
      </main>

      <LandingFooter />
    </div>
  );
}

function NavActionLink({ label }: { label: string }) {
  return (
    <Link
      href="/workspaces"
      className="group inline-flex h-9 items-center gap-2 rounded-full bg-[#B8FF3C] px-5 text-[11px] font-bold tracking-wider text-[#04060F] transition-colors hover:bg-[#caff6a]"
    >
      <span>{label}</span>
      <ArrowRight className="h-3 w-3 transition-transform group-hover:translate-x-0.5" />
    </Link>
  );
}

async function PrimaryNavAction() {
  await connection();
  const { user } = await withAuth();
  return <NavActionLink label={user ? "WORKSPACES" : "LAUNCH SANDBOX"} />;
}
