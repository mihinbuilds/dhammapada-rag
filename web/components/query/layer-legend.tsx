import { LAYER_META, LAYER_ORDER } from "@/lib/layers";
import { cn } from "@/lib/utils";

export function LayerLegend({ className }: { className?: string }) {
  return (
    <div className={cn("flex flex-wrap gap-x-5 gap-y-2", className)}>
      {LAYER_ORDER.map((layer) => {
        const m = LAYER_META[layer];
        return (
          <div key={layer} className="flex items-baseline gap-2">
            <span className={cn("h-2 w-2 rounded-sm relative top-px", m.dot)} />
            <span className="font-sans text-[0.66rem] font-bold uppercase tracking-wide text-ink-soft">
              {m.label}
            </span>
            <span className="font-sans text-[0.73rem] text-ink-faint">{m.desc}</span>
          </div>
        );
      })}
    </div>
  );
}
