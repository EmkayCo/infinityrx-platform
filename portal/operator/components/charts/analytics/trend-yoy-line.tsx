"use client";

import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from "recharts";

interface SpendPoint { period: string; spend: string; year: number; }

interface Props { data: SpendPoint[]; }

export function AnalyticsTrendYoyLine({ data }: Props) {
  // Build side-by-side by month label (strip year)
  const byMonth = new Map<string, { month: string; spend_2025?: number; spend_2026?: number }>();
  for (const row of data) {
    const month = row.period.slice(5);
    const existing = byMonth.get(month) ?? { month };
    if (row.year === 2025) existing.spend_2025 = parseFloat(row.spend);
    else existing.spend_2026 = parseFloat(row.spend);
    byMonth.set(month, existing);
  }
  const chartData = Array.from(byMonth.values()).sort((a, b) => a.month.localeCompare(b.month));

  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" stroke="#E8EAF0" />
        <XAxis dataKey="month" tick={{ fontSize: 11, fill: "#9BA3B5" }} />
        <YAxis
          tick={{ fontSize: 11, fill: "#9BA3B5" }}
          tickFormatter={(v: number) => `$${(v / 1_000_000).toFixed(1)}M`}
        />
        <Tooltip
          contentStyle={{ background: "#fff", border: "1px solid #E8EAF0", borderRadius: 8 }}
          formatter={(v: unknown) => [`$${(Number(v) / 1000).toFixed(0)}K`]}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Line type="monotone" dataKey="spend_2025" name="2025" stroke="#9BA3B5" strokeWidth={2} dot={false} strokeDasharray="5 3" />
        <Line type="monotone" dataKey="spend_2026" name="2026" stroke="#324AB2" strokeWidth={2.5} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}
