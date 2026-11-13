// Abstract orchid petals: cobalt gradient bodies with fine veins, in SVG.
// Purely decorative. Deterministic output (no randomness) so server and client agree.

const PETAL =
  "M0 0 C -90 -80 -140 -260 -40 -420 C 10 -500 120 -470 150 -380 C 200 -230 110 -60 0 0 Z";

const VEINS = Array.from({ length: 19 }, (_, i) => {
  const k = i - 9;
  return `M0 0 Q ${k * 9} -220 ${k * 15 + 5} ${-(370 - Math.abs(k) * 13)}`;
});

export type Petal = {
  x: number;
  y: number;
  rot: number;
  s: number;
  o: number;
  blur?: boolean;
};

export function Petals({
  petals,
  className,
  variant = "default",
}: {
  petals: Petal[];
  className?: string;
  variant?: "default" | "light";
}) {
  return (
    <svg
      aria-hidden
      viewBox="0 0 1200 800"
      preserveAspectRatio="xMidYMid slice"
      className={className}
    >
      <defs>
        <linearGradient id="petal-fill" x1="0" y1="1" x2="0.25" y2="0">
          <stop offset="0" style={{ stopColor: "var(--petal-0)" }} />
          <stop offset="0.45" style={{ stopColor: "var(--petal-1)" }} />
          <stop offset="0.82" style={{ stopColor: "var(--petal-2)" }} />
          <stop offset="1" style={{ stopColor: "var(--petal-3)" }} />
        </linearGradient>
        <linearGradient id="petal-fill-light" x1="0" y1="1" x2="0.25" y2="0">
          <stop offset="0" stopColor="#6f8cf5" />
          <stop offset="0.45" stopColor="#a3b6ff" />
          <stop offset="0.82" stopColor="#d3ddff" />
          <stop offset="1" stopColor="#f4f7ff" />
        </linearGradient>
        <filter id="petal-blur" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="16" />
        </filter>
        <clipPath id="petal-clip">
          <path d={PETAL} />
        </clipPath>
      </defs>
      {petals.map((p, i) => (
        <g
          key={i}
          transform={`translate(${p.x} ${p.y}) rotate(${p.rot}) scale(${p.s})`}
          opacity={p.o}
          filter={p.blur ? "url(#petal-blur)" : undefined}
        >
          <path
            d={PETAL}
            fill={variant === "light" ? "url(#petal-fill-light)" : "url(#petal-fill)"}
          />
          <g
            clipPath="url(#petal-clip)"
            fill="none"
            style={{ stroke: "var(--petal-vein)" }}
            strokeWidth="1.1"
          >
            {VEINS.map((d, j) => (
              <path key={j} d={d} />
            ))}
          </g>
          <path d={PETAL} fill="none" style={{ stroke: "var(--petal-edge)" }} strokeWidth="1.6" />
        </g>
      ))}
    </svg>
  );
}
