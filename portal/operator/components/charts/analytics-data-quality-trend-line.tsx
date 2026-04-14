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
        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 10, fill: "#94A3B8" }}
          tickFormatter={(v: string) => v.slice(5)}
        />
        <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: "#94A3B8" }} />
        <Tooltip
          contentStyle={{
            background: "#1E293B",
            border: "1px solid #334155",
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
