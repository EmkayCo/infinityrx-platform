"use client";

import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend, ReferenceLine,
} from "recharts";

interface PersistencePoint { month: number; pct_with_card: number; pct_without_card: number; }

interface Props { data: PersistencePoint[]; }

export function AnalyticsPersistenceCurve({ data }: Props) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#E8EAF0" />
        <XAxis
          dataKey="month"
          tick={{ fontSize: 11, fill: "#9BA3B5" }}
          label={{ value: "Month", position: "insideBottom", offset: -4, fontSize: 11, fill: "#9BA3B5" }}
        />
        <YAxis
          domain={[0, 100]}
          tick={{ fontSize: 11, fill: "#9BA3B5" }}
          tickFormatter={(v: number) => `${v}%`}
        />
        <Tooltip
          contentStyle={{ background: "#fff", border: "1px solid #E8EAF0", borderRadius: 8 }}
          formatter={(v: unknown) => [`${Number(v)}%`]}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <ReferenceLine y={80} stroke="#F59E0B" strokeDasharray="4 4" label={{ value: "80%", fill: "#F59E0B", fontSize: 10 }} />
        <Line
          type="monotone"
          dataKey="pct_with_card"
          name="With Copay Card"
          stroke="#10B981"
          strokeWidth={2.5}
          dot={false}
        />
        <Line
          type="monotone"
          dataKey="pct_without_card"
          name="Without Copay Card"
          stroke="#EF4444"
          strokeWidth={2.5}
          strokeDasharray="5 3"
          dot={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
