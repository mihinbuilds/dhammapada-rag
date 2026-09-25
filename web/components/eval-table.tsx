import { cn } from "@/lib/utils";

export interface Column {
  header: string;
  align?: "left" | "right";
}

export function EvalTable({
  columns,
  rows,
}: {
  columns: Column[];
  rows: (string | number)[][];
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse font-sans text-[0.82rem]">
        <thead>
          <tr>
            {columns.map((c, i) => (
              <th
                key={i}
                className={cn(
                  "border-b-2 border-ink pb-2 px-2 first:pl-0 text-[0.63rem] font-bold uppercase tracking-wide text-ink-faint",
                  c.align === "right" ? "text-right" : "text-left",
                )}
              >
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => (
            <tr key={ri} className="hover:bg-surface-2/60">
              {row.map((cell, ci) => (
                <td
                  key={ci}
                  className={cn(
                    "py-1.5 px-2 first:pl-0 border-b border-line-soft text-ink",
                    columns[ci]?.align === "right" ? "text-right font-mono tabular-nums" : "text-left",
                  )}
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
