import { useId } from "react";

import { cn } from "@/lib/utils";

/**
 * Relay's brand motif: two lanes, the second picking up where the first leaves off,
 * with the baton (warm dot) travelling across the handover. Decorative only.
 */
export function RelayLines({
  className,
  animated = false,
}: {
  className?: string;
  animated?: boolean;
}) {
  const handover = "M0 230 C 220 230, 300 90, 640 90";
  return (
    <svg
      aria-hidden
      viewBox="0 0 640 300"
      preserveAspectRatio="xMaxYMid slice"
      className={cn("pointer-events-none", className)}
    >
      <path
        d={handover}
        fill="none"
        className="stroke-primary/15"
        strokeWidth="22"
        strokeLinecap="round"
      />
      <path
        d="M90 290 C 300 290, 370 170, 640 170"
        fill="none"
        className="stroke-baton/30"
        strokeWidth="12"
        strokeLinecap="round"
      />
      <path
        d="M-20 150 C 160 150, 260 30, 640 30"
        fill="none"
        className="stroke-primary/[0.07]"
        strokeWidth="8"
        strokeLinecap="round"
      />
      {animated ? (
        <circle
          r="6"
          className="fill-baton relay-baton"
          style={{ offsetPath: `path("${handover}")` }}
        />
      ) : null}
    </svg>
  );
}

/**
 * The Relay mark: a monogram R whose leg hands off to a baton. Crimson lane, lime baton.
 * Decorative; pair it with the "Relay" wordmark or an accessible label.
 */
export function RelayMark({ className }: { className?: string }) {
  const id = useId();
  return (
    <svg aria-hidden viewBox="0 0 32 32" className={cn("shrink-0", className)}>
      <defs>
        <linearGradient
          id={`${id}-lane`}
          x1="6"
          y1="4"
          x2="26"
          y2="28"
          gradientUnits="userSpaceOnUse"
        >
          <stop offset="0" stopColor="#A9BDFF" />
          <stop offset="1" stopColor="#3B5BFF" />
        </linearGradient>
      </defs>
      {/* Stem and bowl: one continuous lane */}
      <path
        d="M9.5 27V5.5h7.6a6.3 6.3 0 0 1 0 12.6H9.5"
        fill="none"
        stroke={`url(#${id}-lane)`}
        strokeWidth="3.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {/* Leg: the handover */}
      <path
        d="M16.8 18.1l5.4 6.4"
        fill="none"
        stroke={`url(#${id}-lane)`}
        strokeWidth="3.4"
        strokeLinecap="round"
      />
      {/* Baton */}
      <circle cx="26" cy="27.6" r="2.3" style={{ fill: "var(--lime)" }} />
      <circle cx="26" cy="27.6" r="4" opacity="0.22" style={{ fill: "var(--lime)" }} />
    </svg>
  );
}
