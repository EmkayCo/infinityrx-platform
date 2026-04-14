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
        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
        <XAxis type="number" tick={{ fontSize: 11, fill: "#94A3B8" }} />
        <YAxis
          type="category"
          dataKey="code"
          tick={{ fontSize: 10, fill: "#94A3B8" }}
          width={60}
        />
        <Tooltip
          formatter={(v) => [`${Number(v)} transactions`]}
          contentStyle={{
            background: "#1E293B",
            border: "1px solid #334155",
            borderRadius: 8,
          }}
        />
        <Bar dataKey="count" fill="#EF4444" radius={[0, 3, 3, 0]} name="Rejections" />
      </BarChart>
    </ResponsiveContainer>
  );
}
