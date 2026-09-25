"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { axisTickStyle, chartTooltipStyle } from "@/components/evaluation/chart-shell";

interface SweepRow {
  model: string;
  max_retries: number;
  n: number;
  clean_rate: number;
  avg_latency_s: number | null;
}

export function SweepChart({ rows }: { rows: SweepRow[] }) {
  const models = Array.from(new Set(rows.map((r) => r.model)));
  const data = models.map((model) => {
    const r0 = rows.find((r) => r.model === model && r.max_retries === 0);
    const r1 = rows.find((r) => r.model === model && r.max_retries === 1);
    return {
      model,
      "max_retries=0": r0?.clean_rate ?? null,
      "max_retries=1": r1?.clean_rate ?? null,
    };
  });

  return (
    <ResponsiveContainer width="100%" height={340} minWidth={420}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--line-soft)" vertical={false} />
        <XAxis dataKey="model" tick={axisTickStyle} axisLine={{ stroke: "var(--line)" }} tickLine={false} />
        <YAxis domain={[0, 1]} tick={axisTickStyle} axisLine={{ stroke: "var(--line)" }} tickLine={false} />
        <Tooltip
          contentStyle={chartTooltipStyle}
          formatter={(v) => (typeof v === "number" ? v.toFixed(3) : "—")}
          cursor={{ fill: "var(--surface-2)" }}
        />
        <Legend wrapperStyle={{ fontFamily: "var(--font-sans)", fontSize: "0.75rem" }} />
        <Bar dataKey="max_retries=0" fill="var(--ink)" radius={[4, 4, 0, 0]} maxBarSize={36} />
        <Bar dataKey="max_retries=1" fill="var(--ink-faint)" radius={[4, 4, 0, 0]} maxBarSize={36} />
      </BarChart>
    </ResponsiveContainer>
  );
}
