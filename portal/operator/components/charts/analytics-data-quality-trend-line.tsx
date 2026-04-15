"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

interface TrendPoint {
  date: string;
  score: number;
}

interface Props {
  data: TrendPoint[];
}

export function AnalyticsDataQualityTrendLine({ data }: Props) {
  return (
    <ResponsiveContainer width="100%" height={160}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 10, fill: "var(--fg-muted)" }}
          tickFormatter={(v: string) => v.slice(5)}
        />
        <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: "var(--fg-muted)" }} />
        <Tooltip
          contentStyle={{
            background: "var(--bg-card-alt)", color: "var(--fg)",
            border: "1px solid var(--border)",
            borderRadius: 8,
          }}
        />
        <Line
          type="monotone"
          dataKey="score"
          stroke="#00B4D8"
          strokeWidth={2}
          dot={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
