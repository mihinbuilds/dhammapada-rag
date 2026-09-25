import type { ReactNode } from "react";

export function ChartShell({
  title,
  caption,
  children,
}: {
  title: string;
  caption?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="rounded-xl border border-line bg-surface p-4 sm:p-5">
      <p className="font-serif text-[0.9rem] font-semibold text-ink mb-3">{title}</p>
      <div className="w-full overflow-x-auto">{children}</div>
      {caption && (
        <p className="mt-3 font-sans text-[0.78rem] leading-relaxed text-ink-faint">{caption}</p>
      )}
    </div>
  );
}

export const chartTooltipStyle = {
  background: "var(--surface)",
  border: "1px solid var(--line)",
  borderRadius: 8,
  fontFamily: "var(--font-sans)",
  fontSize: "0.78rem",
  color: "var(--ink)",
  boxShadow: "0 4px 16px rgba(0,0,0,0.08)",
};

export const axisTickStyle = {
  fontFamily: "var(--font-sans)",
  fontSize: 11,
  fill: "var(--ink-faint)",
};
