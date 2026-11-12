const ROWS: ReadonlyArray<readonly [label: string, value: string]> = [
  ["Blast radius", "35 mm"],
  ["Blast radius", "254 mm"],
  ["Last radius", "75 npc"],
];

/** Frosted telemetry readout anchored to the hero capsule. Decorative sample data. */
export function BlastRadiusCard() {
  return (
    <div className="glass-clear relative w-44 p-4 select-none sm:w-48">
      {/* Card Header */}
      <div className="mb-3 flex items-center justify-between border-b border-white/10 pb-2.5">
        <span className="font-mono text-[10px] font-medium tracking-[0.22em] text-zinc-400 uppercase">
          BLAST RADIUS
        </span>
        <span className="h-1.5 w-1.5 rounded-full bg-[#C4FF00] shadow-[0_0_8px_#C4FF00]" />
      </div>

      {/* Telemetry Metric Rows */}
      <dl className="space-y-2 font-mono text-xs">
        {ROWS.map(([label, value], i) => (
          <div key={i} className="flex items-center justify-between">
            <dt className="text-[11px] tracking-wide text-zinc-300">{label}</dt>
            <dd className="font-semibold tracking-wider text-white">{value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
