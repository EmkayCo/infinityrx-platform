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

interface PriceHistoryRow {
  date: string;
  AWP: number;
  WAC: number;
  NADAC: number | null;
}

interface Props {
  data: PriceHistoryRow[];
}

export function DirectoriesDrugPriceHistoryLine({ data }: Props) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis dataKey="date" tick={{ fontSize: 11, fill: "var(--fg-muted)" }} />
        <YAxis
          tick={{ fontSize: 11, fill: "var(--fg-muted)" }}
          tickFormatter={(v: number) => `$${Number(v)}`}
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
          dataKey="AWP"
          stroke="#00B4D8"
          strokeWidth={2}
          dot={false}
        />
        <Line
          type="monotone"
          dataKey="WAC"
          stroke="#F59E0B"
          strokeWidth={2}
          dot={false}
        />
        <Line
          type="monotone"
          dataKey="NADAC"
          stroke="#10B981"
          strokeWidth={2}
          dot={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
