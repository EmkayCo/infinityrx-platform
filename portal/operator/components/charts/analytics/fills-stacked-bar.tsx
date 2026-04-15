"use client";

import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from "recharts";

interface FillPeriod { period: string; new_starts: number; refills: number; }

interface Props { data: FillPeriod[]; }

export function AnalyticsFillsStackedBar({ data }: Props) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#E8EAF0" />
        <XAxis dataKey="period" tick={{ fontSize: 11, fill: "#9BA3B5" }} tickFormatter={(v: string) => v.slice(5)} />
        <YAxis tick={{ fontSize: 11, fill: "#9BA3B5" }} />
        <Tooltip
          contentStyle={{ background: "#fff", border: "1px solid #E8EAF0", borderRadius: 8 }}
          formatter={(v: unknown) => [Number(v).toLocaleString()]}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Bar dataKey="new_starts" name="New Starts (NBRx)" stackId="a" fill="#19286B" />
        <Bar dataKey="refills" name="Refills" stackId="a" fill="#324AB2" radius={[3, 3, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
