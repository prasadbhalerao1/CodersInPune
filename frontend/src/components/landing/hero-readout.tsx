import { ArrowRight } from "lucide-react";
import Link from "next/link";

/** The simulator's default scenario (Arjun away two weeks), previewed in the hero. */
export function HeroReadout() {
  return (
    <Link href="#simulator" className="glass-dark group block w-64 p-4 text-left">
      <p className="text-fg-soft text-xs">What if Arjun is away for 2 weeks?</p>
      <p className="mt-2 flex items-baseline gap-2">
        <span className="font-display text-strong text-5xl leading-none tabular-nums">55</span>
        <span className="text-sm font-medium" style={{ color: "var(--bad)" }}>
          At risk
        </span>
      </p>
      <div className="bg-line/10 mt-3 h-1 overflow-clip rounded-full">
        <div className="h-full w-[55%] rounded-full" style={{ background: "var(--bad)" }} />
      </div>
      <p className="text-fg-soft mt-3 text-xs leading-snug">
        2 critical responsibilities have no backup.
      </p>
      <span className="text-ac mt-3 inline-flex items-center gap-1 text-xs font-medium">
        Run the simulator
        <ArrowRight
          className="h-3 w-3 transition-transform group-hover:translate-x-0.5"
          aria-hidden
        />
      </span>
    </Link>
  );
}
