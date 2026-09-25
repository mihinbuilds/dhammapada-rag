import type { VaggaOut } from "@/lib/api";
import { cn } from "@/lib/utils";

export function VaggaNav({
  vaggas,
  activeNumber,
  onSelect,
}: {
  vaggas: VaggaOut[];
  activeNumber: number | null;
  onSelect: (v: VaggaOut) => void;
}) {
  return (
    <div className="rounded-xl border border-line bg-surface overflow-hidden">
      <p className="px-3.5 pt-3 pb-2 font-sans text-[0.66rem] font-bold uppercase tracking-wide text-ink-faint">
        26 vaggas
      </p>
      <div className="max-h-[420px] overflow-y-auto scrollbar-thin divide-y divide-line-soft">
        {vaggas.map((v) => (
          <button
            key={v.number}
            type="button"
            onClick={() => onSelect(v)}
            className={cn(
              "w-full text-left px-3.5 py-2.5 transition-colors",
              activeNumber === v.number ? "bg-surface-2" : "hover:bg-surface-2/60",
            )}
          >
            <div className="flex items-baseline justify-between gap-2">
              <span className="font-serif text-[0.86rem] text-ink">
                {v.number}. {v.name_pali}
              </span>
              <span className="font-mono text-[0.64rem] text-ink-faint whitespace-nowrap">
                {v.first_verse}–{v.last_verse}
              </span>
            </div>
            <p className="font-sans text-[0.72rem] text-ink-faint mt-0.5">{v.name_en}</p>
          </button>
        ))}
      </div>
    </div>
  );
}
