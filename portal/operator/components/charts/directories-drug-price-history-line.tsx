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
        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
        <XAxis dataKey="date" tick={{ fontSize: 11, fill: "#94A3B8" }} />
        <YAxis
          tick={{ fontSize: 11, fill: "#94A3B8" }}
          tickFormatter={(v: number) => `$${Number(v)}`}
        />
        <Tooltip
          formatter={(v) => [`$${Number(v).toFixed(2)}`]}
          contentStyle={{
            background: "#1E293B",
            border: "1px solid #334155",
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
