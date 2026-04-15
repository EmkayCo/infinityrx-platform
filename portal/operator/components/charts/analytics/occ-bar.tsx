"use client";

import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";

interface OccRow { occ: string; count: number; pct: number; }

interface Props { data: OccRow[]; }

export function AnalyticsOccBar({ data }: Props) {
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data} layout="vertical">
        <CartesianGrid strokeDasharray="3 3" stroke="#E8EAF0" horizontal={false} />
        <XAxis type="number" tick={{ fontSize: 11, fill: "#9BA3B5" }} />
        <YAxis
          dataKey="occ"
          type="category"
          width={200}
          tick={{ fontSize: 11, fill: "#374151" }}
        />
        <Tooltip
          contentStyle={{ background: "#fff", border: "1px solid #E8EAF0", borderRadius: 8 }}
          formatter={(v: unknown) => [Number(v).toLocaleString()]}
        />
        <Bar dataKey="count" name="Claims" fill="#324AB2" radius={[0, 3, 3, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
