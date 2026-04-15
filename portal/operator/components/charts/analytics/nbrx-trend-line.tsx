"use client";

import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from "recharts";

interface NbrxPoint { period: string; nbrx: number; trx: number; }

interface Props { data: NbrxPoint[]; }

export function AnalyticsNbrxTrendLine({ data }: Props) {
  return (
    <ResponsiveContainer width="100%" height={240}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#E8EAF0" />
        <XAxis dataKey="period" tick={{ fontSize: 11, fill: "#9BA3B5" }} tickFormatter={(v: string) => v.slice(5)} />
        <YAxis tick={{ fontSize: 11, fill: "#9BA3B5" }} />
        <Tooltip
          contentStyle={{ background: "#fff", border: "1px solid #E8EAF0", borderRadius: 8 }}
          formatter={(v: unknown) => [Number(v).toLocaleString()]}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Line type="monotone" dataKey="nbrx" name="NBRx (New Starts)" stroke="#FF77FF" strokeWidth={2} dot={false} />
        <Line type="monotone" dataKey="trx" name="TRx (Total)" stroke="#324AB2" strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}
