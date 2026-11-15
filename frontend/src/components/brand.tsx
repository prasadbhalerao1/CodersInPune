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
 * The Relay mark: a solid R whose leg has been handed over, a step apart from the body and in
 * the baton colour. The leg arrives a beat late (`.mark-leg` in globals.css) and leans in on
 * hover of a `.mark-link`. Decorative; pair it with the "Relay" wordmark or an accessible label.
 */
export function RelayMark({ className }: { className?: string }) {
  const id = useId();
  return (
    <svg aria-hidden viewBox="0 0 32 32" className={cn("shrink-0", className)}>
      <defs>
        <linearGradient
          id={`${id}-body`}
          x1="6"
          y1="4"
          x2="22"
          y2="28"
          gradientUnits="userSpaceOnUse"
        >
          <stop offset="0" style={{ stopColor: "var(--mark-a)" }} />
          <stop offset="1" style={{ stopColor: "var(--mark-b)" }} />
        </linearGradient>
      </defs>
      {/* Stem and bowl, with the counter cut out */}
      <path
        d="M6 4h11a7 7 0 0 1 0 14h-5v10H6zM12 9v4h4.6a2 2 0 0 0 0-4z"
        fillRule="evenodd"
        fill={`url(#${id}-body)`}
      />
      {/* The leg: the piece that was handed over */}
      <path className="mark-leg" d="M15.4 20h6l5.6 8h-6z" style={{ fill: "var(--mark-leg)" }} />
    </svg>
  );
}
