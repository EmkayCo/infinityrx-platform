"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

interface RejectionCode {
  code: string;
  count: number;
}

interface Props {
  data: RejectionCode[];
}

export function EdiMonitorRejectionBar({ data }: Props) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data.slice(0, 10)} layout="vertical">
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis type="number" tick={{ fontSize: 11, fill: "var(--fg-muted)" }} />
        <YAxis
          type="category"
          dataKey="code"
          tick={{ fontSize: 10, fill: "var(--fg-muted)" }}
          width={60}
        />
        <Tooltip
          formatter={(v) => [`${Number(v)} transactions`]}
          contentStyle={{
            background: "var(--bg-card-alt)", color: "var(--fg)",
            border: "1px solid var(--border)",
            borderRadius: 8,
          }}
        />
        <Bar dataKey="count" fill="#EF4444" radius={[0, 3, 3, 0]} name="Rejections" />
      </BarChart>
    </ResponsiveContainer>
  );
}
