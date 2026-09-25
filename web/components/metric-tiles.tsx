export interface MetricTile {
  label: string;
  value: string | number;
  sub?: string | null;
}

export function MetricTiles({ items }: { items: MetricTile[] }) {
  if (!items.length) return null;
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
      {items.map((item, i) => (
        <div
          key={i}
          className="flex flex-col rounded-xl border border-line bg-surface px-4 py-3.5 min-h-[5.4rem]"
        >
          <span className="font-sans text-[0.63rem] font-bold uppercase tracking-wide text-ink-faint leading-snug">
            {item.label}
          </span>
          <span className="font-serif text-[1.5rem] font-semibold text-ink mt-1 tabular-nums leading-none">
            {item.value}
          </span>
          <span className="font-mono text-[0.67rem] text-ink-faint mt-auto pt-1.5 min-h-[0.9rem]">
            {item.sub ?? ""}
          </span>
        </div>
      ))}
    </div>
  );
}
