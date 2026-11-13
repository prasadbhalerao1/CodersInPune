import type { ReactNode } from "react";

export function Feature({
  id,
  kicker,
  tone,
  title,
  accent,
  className = "",
  children,
}: {
  id?: string;
  kicker: string;
  tone: string;
  title: string;
  accent: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div id={id} className={`glass reveal flex scroll-mt-24 flex-col p-7 ${className}`}>
      <span className="text-sm font-semibold" style={{ color: tone }}>
        {kicker}
      </span>
      <h3 className="font-display text-strong mt-4 text-[2.7rem] leading-[0.98] tracking-[-0.01em]">
        {title}{" "}
        <span className="italic" style={{ color: tone }}>
          {accent}
        </span>
      </h3>
      {children}
    </div>
  );
}

export function Chip({ children, tone = "#9CA3AF" }: { children: ReactNode; tone?: string }) {
  return (
    <span
      className="rounded-md border px-2 py-0.5 text-xs font-medium whitespace-nowrap"
      style={{
        color: tone,
        borderColor: `color-mix(in srgb, ${tone} 35%, transparent)`,
        background: `color-mix(in srgb, ${tone} 10%, transparent)`,
      }}
    >
      {children}
    </span>
  );
}

export const body = "mt-4 mb-5 text-sm leading-relaxed text-fg-mute";
export const panel = "mt-auto border-t border-line/15 pt-4";
