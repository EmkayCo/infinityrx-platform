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
import type { DrugTrendPoint } from "@shared/types/analytics";

interface Props {
  data: DrugTrendPoint[];
}

export function AnalyticsDrugTrendSpendLine({ data }: Props) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={data.map((d) => ({ ...d, spend_num: parseFloat(d.spend) }))}>
        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 11, fill: "#94A3B8" }}
          tickFormatter={(v: string) => v.slice(5)}
        />
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
        <Line
          type="monotone"
          dataKey="spend_num"
          stroke="#00B4D8"
          strokeWidth={2}
          dot={false}
          name="Spend"
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
