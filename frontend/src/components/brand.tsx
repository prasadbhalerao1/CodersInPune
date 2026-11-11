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
