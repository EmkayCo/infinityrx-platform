"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { FinancialMetrics } from "@shared/types/analytics";

type CostDriverRow = FinancialMetrics["cost_driver_breakdown"][number];

interface Props {
  data: CostDriverRow[];
}

export function AnalyticsFinancialCostDriverBar({ data }: Props) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart
        data={data.map((d) => ({
          category: d.category,
          amount: parseFloat(d.amount),
          pct: d.pct_of_total,
        }))}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis dataKey="category" tick={{ fontSize: 10, fill: "var(--fg-muted)" }} />
        <YAxis
          tick={{ fontSize: 10, fill: "var(--fg-muted)" }}
          tickFormatter={(v: number) => `$${(v / 1000000).toFixed(1)}M`}
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
        <Bar dataKey="amount" fill="#00B4D8" name="Amount" radius={[3, 3, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
