"use client";

import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from "recharts";

interface ClaimStatus {
  period: string;
  paid: number;
  reversed: number;
  pending: number;
  rejected: number;
}

interface Props {
  data: ClaimStatus[];
}

export function AnalyticsClaimStatusStackedBar({ data }: Props) {
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
        <Bar dataKey="paid" name="Paid" stackId="a" fill="#10B981" />
        <Bar dataKey="reversed" name="Reversed" stackId="a" fill="#EF4444" />
        <Bar dataKey="pending" name="Pending" stackId="a" fill="#F59E0B" />
        <Bar dataKey="rejected" name="Rejected" stackId="a" fill="#9BA3B5" radius={[3, 3, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
