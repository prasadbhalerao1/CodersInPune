import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/** Fine grid plus a soft glow: the same atmosphere as the hero, scaled down for sections. */
export function SectionBackdrop({
  className,
}: {
  tone?: "lime" | "red" | "blue";
  className?: string;
}) {
  return (
    <div
      aria-hidden
      className={cn("pointer-events-none absolute inset-0 overflow-hidden", className)}
    >
      <div
        className="absolute inset-0 opacity-[0.045]"
        style={{
          backgroundImage:
            "linear-gradient(#fff 1px, transparent 1px), linear-gradient(90deg, #fff 1px, transparent 1px)",
          backgroundSize: "64px 64px",
          maskImage: "radial-gradient(ellipse at 50% 30%, #000, transparent 75%)",
        }}
      />
    </div>
  );
}

/** Eyebrow + Bebas headline + optional description. `accent` is rendered lime. */
export function SectionHeading({
  eyebrow,
  title,
  accent,
  description,
  align = "center",
  theme = "crimson",
  className,
  children,
}: {
  eyebrow: string;
  title: string;
  accent?: string;
  description?: ReactNode;
  align?: "center" | "left";
  theme?: "crimson" | "blue";
  className?: string;
  children?: ReactNode;
}) {
  const center = align === "center";
  const blue = theme === "blue";
  return (
    <div
      className={cn(
        "reveal flex flex-col gap-4",
        center ? "mx-auto max-w-5xl items-center text-center" : "items-start",
        className,
      )}
    >
      {blue ? (
        <>
          <span className="text-sm font-medium text-[#8FA8FF]">{eyebrow}</span>
          <h2 className="font-display text-[clamp(3rem,7vw,6.2rem)] leading-[0.96] tracking-[-0.01em] text-[#F2EEE5]">
            {title}
            {accent ? <span className="block text-[#B8FF3C] italic">{accent}</span> : null}
          </h2>
        </>
      ) : (
        <>
          <span className="text-sm font-medium text-[#C4FF00]">{eyebrow}</span>
          <h2 className="font-bebas text-[clamp(2.8rem,6.4vw,5.6rem)] leading-[0.92] tracking-[0.005em] text-[#F1EDE6] uppercase">
            {title}
            {accent ? <span className="block text-[#C4FF00]">{accent}</span> : null}
          </h2>
        </>
      )}
      {description ? (
        <p
          className={cn(
            "max-w-xl text-[0.95rem] leading-relaxed",
            blue ? "text-slate-400" : "text-zinc-400",
          )}
        >
          {description}
        </p>
      ) : null}
      {children}
    </div>
  );
}
