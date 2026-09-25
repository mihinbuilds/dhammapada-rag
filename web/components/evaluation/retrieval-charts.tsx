"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ErrorBar,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { axisTickStyle, chartTooltipStyle } from "@/components/evaluation/chart-shell";

interface ByTypeRow {
  type: string;
  n: number;
  "recall@1": number;
  "recall@10": number;
  "ndcg@10": number;
  mrr: number;
}

export function RetrievalByTypeChart({ rows, worst }: { rows: ByTypeRow[]; worst: string | null }) {
  const sorted = [...rows].sort((a, b) => b["ndcg@10"] - a["ndcg@10"]);
  return (
    <ResponsiveContainer width="100%" height={320} minWidth={480}>
      <BarChart data={sorted} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--line-soft)" vertical={false} />
        <XAxis dataKey="type" tick={axisTickStyle} axisLine={{ stroke: "var(--line)" }} tickLine={false} />
        <YAxis domain={[0, 1]} tick={axisTickStyle} axisLine={{ stroke: "var(--line)" }} tickLine={false} />
        <Tooltip
          contentStyle={chartTooltipStyle}
          formatter={(v) => (typeof v === "number" ? v.toFixed(3) : String(v))}
          cursor={{ fill: "var(--surface-2)" }}
        />
        <Bar dataKey="ndcg@10" radius={[4, 4, 0, 0]} maxBarSize={48}>
          {sorted.map((r) => (
            <Cell key={r.type} fill={r.type === worst ? "var(--error)" : "var(--ink-soft)"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

interface AblationRow {
  key: string;
  label: string;
  delta: number;
  errPlus: number;
  errMinus: number;
}

export function AblationChart({ rows }: { rows: AblationRow[] }) {
  const data = rows.map((r) => ({ ...r, err: [r.errMinus, r.errPlus] as [number, number] }));
  return (
    <ResponsiveContainer width="100%" height={320} minWidth={420}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--line-soft)" vertical={false} />
        <XAxis dataKey="label" tick={axisTickStyle} axisLine={{ stroke: "var(--line)" }} tickLine={false} />
        <YAxis tick={axisTickStyle} axisLine={{ stroke: "var(--line)" }} tickLine={false} />
        <Tooltip
          contentStyle={chartTooltipStyle}
          formatter={(v) => (typeof v === "number" ? v.toFixed(3) : String(v))}
          cursor={{ fill: "var(--surface-2)" }}
        />
        <Bar dataKey="delta" radius={[4, 4, 0, 0]} maxBarSize={56}>
          {data.map((r) => (
            <Cell key={r.key} fill={r.key === "verse_only" ? "var(--ink)" : "var(--ink-faint)"} />
          ))}
          <ErrorBar dataKey="err" stroke="var(--ink-soft)" width={4} />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
