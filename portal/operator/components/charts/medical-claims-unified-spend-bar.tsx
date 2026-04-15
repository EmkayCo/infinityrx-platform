"use client";

import {
  ComposedChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";

interface ChartRow {
  month: string;
  Pharmacy: number;
  Medical: number;
}

interface Props {
  data: ChartRow[];
}

export function MedicalClaimsUnifiedSpendBar({ data }: Props) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <ComposedChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis dataKey="month" tick={{ fontSize: 11, fill: "var(--fg-muted)" }} />
        <YAxis
          tick={{ fontSize: 11, fill: "var(--fg-muted)" }}
          tickFormatter={(v: number) => `$${(v / 1000).toFixed(0)}K`}
        />
        <Tooltip
          formatter={(v) => [
            `$${Number(v).toLocaleString("en-US", { minimumFractionDigits: 2 })}`,
          ]}
          contentStyle={{
            background: "var(--bg-card-alt)", color: "var(--fg)",
            border: "1px solid var(--border)",
            borderRadius: 8,
          }}
        />
        <Legend />
        <Bar dataKey="Pharmacy" fill="#00B4D8" name="Pharmacy Spend" radius={[3, 3, 0, 0]} />
        <Bar dataKey="Medical" fill="#8B5CF6" name="Medical Spend" radius={[3, 3, 0, 0]} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
