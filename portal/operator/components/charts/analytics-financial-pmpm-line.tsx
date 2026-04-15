"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import type { FinancialMetrics } from "@shared/types/analytics";

type PmpmTrendRow = FinancialMetrics["pmpm_trend"][number];

interface Props {
  data: PmpmTrendRow[];
}

export function AnalyticsFinancialPmpmLine({ data }: Props) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart
        data={data.map((d) => ({
          month: d.month,
          current: parseFloat(d.pmpm),
          prior_year: parseFloat(d.prior_year_pmpm),
        }))}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis
          dataKey="month"
          tick={{ fontSize: 10, fill: "var(--fg-muted)" }}
          tickFormatter={(v: string) => v.slice(5)}
        />
        <YAxis
          tick={{ fontSize: 10, fill: "var(--fg-muted)" }}
          tickFormatter={(v: number) => `$${Number(v).toFixed(0)}`}
        />
        <Tooltip
          formatter={(v) => [`$${Number(v).toFixed(2)}`]}
          contentStyle={{
            background: "var(--bg-card-alt)", color: "var(--fg)",
            border: "1px solid var(--border)",
            borderRadius: 8,
          }}
        />
        <Legend />
        <Line
          type="monotone"
          dataKey="current"
          stroke="#00B4D8"
          strokeWidth={2}
          dot={false}
          name="Current Year"
        />
        <Line
          type="monotone"
          dataKey="prior_year"
          stroke="#6B7280"
          strokeWidth={2}
          dot={false}
          strokeDasharray="5 5"
          name="Prior Year"
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
