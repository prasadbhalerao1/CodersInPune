import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/** Eyebrow, display headline with an italic accent, and an optional description. */
export function SectionHeading({
  eyebrow,
  title,
  accent,
  description,
  align = "center",
  theme = "crimson",
  compact = false,
  className,
  children,
}: {
  eyebrow: string;
  title: string;
  accent?: string;
  description?: ReactNode;
  align?: "center" | "left";
  theme?: "crimson" | "blue";
  /** For headings inside a column: smaller, so long words never run into the next column. */
  compact?: boolean;
  className?: string;
  children?: ReactNode;
}) {
  const center = align === "center";
  const blue = theme === "blue";
  return (
    <div
      className={cn(
        "reveal scrim flex flex-col gap-4",
        center ? "mx-auto max-w-5xl items-center text-center" : "items-start",
        className,
      )}
    >
      {blue ? (
        <>
          <span className="text-peri text-sm font-medium">{eyebrow}</span>
          <h2
            className={cn(
              "font-display text-strong tracking-[-0.01em] text-balance",
              compact ? "text-[clamp(2.6rem,4.6vw,4.6rem)]" : "text-[clamp(3rem,7vw,6.2rem)]",
              "leading-[0.96]",
            )}
          >
            {title}
            {accent ? <span className="text-ac block italic">{accent}</span> : null}
          </h2>
        </>
      ) : (
        <>
          <span className="text-ac text-sm font-medium">{eyebrow}</span>
          <h2 className="font-bebas text-strong text-[clamp(2.8rem,6.4vw,5.6rem)] leading-[0.92] tracking-[0.005em] uppercase">
            {title}
            {accent ? <span className="text-ac block">{accent}</span> : null}
          </h2>
        </>
      )}
      {description ? (
        <p
          className={cn(
            "max-w-xl text-[0.95rem] leading-relaxed",
            blue ? "text-fg-mute" : "text-fg-mute",
          )}
        >
          {description}
        </p>
      ) : null}
      {children}
    </div>
  );
}
