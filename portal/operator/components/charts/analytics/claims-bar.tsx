"use client";

import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from "recharts";

interface ClaimPeriod {
  period: string;
  net_claim_count: number;
  new_enrollments: number;
}

interface Props {
  data: ClaimPeriod[];
  onBarClick?: (period: string) => void;
}

export function AnalyticsClaimsBar({ data, onBarClick }: Props) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={data} onClick={(e) => {
        if (e?.activeLabel && onBarClick) onBarClick(String(e.activeLabel));
      }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--ifx-gray-100, #E8EAF0)" />
        <XAxis
          dataKey="period"
          tick={{ fontSize: 11, fill: "#9BA3B5" }}
          tickFormatter={(v: string) => v.slice(5)}
        />
        <YAxis tick={{ fontSize: 11, fill: "#9BA3B5" }} />
        <Tooltip
          contentStyle={{ background: "#fff", border: "1px solid #E8EAF0", borderRadius: 8 }}
          formatter={(v: unknown) => [Number(v).toLocaleString()]}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Bar dataKey="net_claim_count" name="Net Claims" fill="#324AB2" radius={[3, 3, 0, 0]} cursor="pointer" />
        <Bar dataKey="new_enrollments" name="New Enrollments" fill="#10B981" radius={[3, 3, 0, 0]} cursor="pointer" />
      </BarChart>
    </ResponsiveContainer>
  );
}
