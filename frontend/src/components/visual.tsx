import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

// Muted, distinguishable tones for people. Chosen by name so a person keeps their colour.
const AVATAR_TONES = [
  "bg-teal-100 text-teal-800 dark:bg-teal-950 dark:text-teal-200",
  "bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-200",
  "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-200",
  "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-200",
  "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200",
  "bg-slate-200 text-slate-800 dark:bg-slate-800 dark:text-slate-200",
  "bg-orange-100 text-orange-800 dark:bg-orange-950 dark:text-orange-200",
  "bg-cyan-100 text-cyan-800 dark:bg-cyan-950 dark:text-cyan-200",
];

function hash(text: string): number {
  let h = 0;
  for (const ch of text) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return h;
}

export function initials(name: string): string {
  const parts = name
    .replace(/\(.*?\)/g, "")
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  return ((parts[0]?.[0] ?? "?") + (parts.length > 1 ? parts.at(-1)![0] : "")).toUpperCase();
}

export function Avatar({
  name,
  size = "md",
  className,
}: {
  name: string;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const sizes = { sm: "size-6 text-[10px]", md: "size-8 text-xs", lg: "size-10 text-sm" };
  return (
    <span
      title={name}
      className={cn(
        "ring-background inline-flex shrink-0 items-center justify-center rounded-full font-semibold ring-2",
        sizes[size],
        AVATAR_TONES[hash(name) % AVATAR_TONES.length],
        className,
      )}
    >
      {initials(name)}
    </span>
  );
}

const TILE_TONES = {
  primary: "bg-accent text-accent-foreground",
  danger: "bg-red-50 text-red-700 dark:bg-red-950/50 dark:text-red-300",
  warning: "bg-amber-50 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300",
  success: "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300",
  neutral: "bg-muted text-muted-foreground",
} as const;
export type TileTone = keyof typeof TILE_TONES;

export function IconTile({
  icon: Icon,
  tone = "primary",
  className,
}: {
  icon: LucideIcon;
  tone?: TileTone;
  className?: string;
}) {
  return (
    <span
      aria-hidden
      className={cn(
        "inline-flex size-8 shrink-0 items-center justify-center rounded-md",
        TILE_TONES[tone],
        className,
      )}
    >
      <Icon className="size-4" />
    </span>
  );
}

/** A ring gauge for a 0–100 value. The arc draws in on mount. */
export function Ring({
  value,
  size = 112,
  stroke = 10,
  tone = "primary",
  children,
}: {
  value: number;
  size?: number;
  stroke?: number;
  tone?: "primary" | "success" | "warning" | "danger";
  children?: ReactNode;
}) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const clamped = Math.max(0, Math.min(100, value));
  const colour = {
    primary: "stroke-primary",
    success: "stroke-emerald-600",
    warning: "stroke-amber-500",
    danger: "stroke-red-600",
  }[tone];
  return (
    <div className="relative inline-flex shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          strokeWidth={stroke}
          className="stroke-muted fill-none"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          strokeWidth={stroke}
          strokeLinecap="round"
          className={cn("ring-draw fill-none", colour)}
          style={
            {
              strokeDasharray: c,
              strokeDashoffset: c * (1 - clamped / 100),
              "--ring-c": c,
            } as React.CSSProperties
          }
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
        {children}
      </div>
    </div>
  );
}

/** A stacked horizontal bar with a legend: parts of one whole. */
export function SegmentBar({
  segments,
  label,
}: {
  segments: { label: string; value: number; className: string }[];
  label: string;
}) {
  const total = segments.reduce((sum, s) => sum + s.value, 0);
  return (
    <div className="flex flex-col gap-2">
      <div
        role="img"
        aria-label={`${label}: ${segments.map((s) => `${s.value} ${s.label}`).join(", ")}`}
        className="bg-muted flex h-2 overflow-hidden rounded-full"
      >
        {total > 0
          ? segments
              .filter((s) => s.value > 0)
              .map((s) => (
                <span
                  key={s.label}
                  className={cn("motion-fill h-full", s.className)}
                  style={{ width: `${(s.value / total) * 100}%` }}
                />
              ))
          : null}
      </div>
      <ul className="text-muted-foreground flex flex-wrap gap-x-4 gap-y-1 text-xs">
        {segments.map((s) => (
          <li key={s.label} className="flex items-center gap-1.5">
            <span aria-hidden className={cn("size-2 rounded-full", s.className)} />
            <span className="text-foreground tabular font-medium">{s.value}</span> {s.label}
          </li>
        ))}
      </ul>
    </div>
  );
}

const relative = new Intl.RelativeTimeFormat("en-GB", { numeric: "auto" });
const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 31_536_000],
  ["month", 2_592_000],
  ["week", 604_800],
  ["day", 86_400],
  ["hour", 3_600],
  ["minute", 60],
];

/** "3 days ago" / "in 2 weeks"; the exact time is in the tooltip. */
export function RelativeTime({ iso, now }: { iso: string; now: number }) {
  const seconds = (new Date(iso).getTime() - now) / 1000;
  const [unit, size] = UNITS.find(([, s]) => Math.abs(seconds) >= s) ?? ["second", 1];
  const text = unit === "second" ? "just now" : relative.format(Math.round(seconds / size), unit);
  return (
    <time dateTime={iso} title={new Date(iso).toLocaleString("en-GB")}>
      {text}
    </time>
  );
}
