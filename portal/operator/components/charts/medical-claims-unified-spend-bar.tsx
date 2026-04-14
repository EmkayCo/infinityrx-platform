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
        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
        <XAxis dataKey="month" tick={{ fontSize: 11, fill: "#94A3B8" }} />
        <YAxis
          tick={{ fontSize: 11, fill: "#94A3B8" }}
          tickFormatter={(v: number) => `$${(v / 1000).toFixed(0)}K`}
        />
        <Tooltip
          formatter={(v) => [
            `$${Number(v).toLocaleString("en-US", { minimumFractionDigits: 2 })}`,
          ]}
          contentStyle={{
            background: "#1E293B",
            border: "1px solid #334155",
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
