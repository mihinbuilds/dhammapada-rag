import { LAYER_ORDER } from "@/lib/layers";
import type { Layer } from "@/lib/api";

export function ConfusionMatrix({ matrix }: { matrix: Record<string, Record<string, number>> }) {
  const layers = [
    ...LAYER_ORDER.filter((l) => l in matrix),
    ...Object.keys(matrix).filter((l) => !LAYER_ORDER.includes(l as Layer)),
  ];
  const maxV = Math.max(
    1,
    ...layers.flatMap((g) => layers.map((p) => matrix[g]?.[p] ?? 0)),
  );

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse font-sans text-[0.82rem]">
        <thead>
          <tr>
            <th className="w-36 text-left border-b-2 border-ink pb-2 pr-2 text-[0.63rem] font-bold uppercase tracking-wide text-ink-faint">
              gold \ pred
            </th>
            {layers.map((l) => (
              <th
                key={l}
                className="text-right border-b-2 border-ink pb-2 px-2 text-[0.63rem] font-bold uppercase tracking-wide text-ink-faint"
              >
                {l}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {layers.map((g) => (
            <tr key={g}>
              <td className="text-left py-1.5 pr-2 border-b border-line-soft font-semibold text-ink">
                {g}
              </td>
              {layers.map((p) => {
                const v = matrix[g]?.[p] ?? 0;
                const alpha = v ? 0.16 * (v / maxV) : 0;
                return (
                  <td key={p} className="text-right py-1.5 px-2 border-b border-line-soft">
                    <span
                      className="inline-block rounded px-2 py-0.5 tabular-nums"
                      style={{ background: `rgb(var(--shadow-color) / ${alpha.toFixed(3)})` }}
                    >
                      {v || "·"}
                    </span>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
