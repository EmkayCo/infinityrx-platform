"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Cell,
} from "recharts";

const REJECT_COLOR = (rate: number) => {
  if (rate <= 5) return "#10B981";
  if (rate <= 10) return "#F59E0B";
  return "#EF4444";
};

interface RejectRateRow {
  name: string;
  reject_rate: number;
  mac_ratio: number;
  tier: string;
}

interface Props {
  data: RejectRateRow[];
}

export function AnalyticsNetworkRejectRateBar({ data }: Props) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis dataKey="name" tick={{ fontSize: 10, fill: "var(--fg-muted)" }} />
        <YAxis
          tick={{ fontSize: 10, fill: "var(--fg-muted)" }}
          tickFormatter={(v: number) => `${Number(v)}%`}
        />
        <Tooltip
          formatter={(v) => [`${Number(v).toFixed(1)}%`, "Reject Rate"]}
          contentStyle={{
            background: "var(--bg-card-alt)", color: "var(--fg)",
            border: "1px solid var(--border)",
            borderRadius: 8,
          }}
        />
        <ReferenceLine
          y={10}
          stroke="#F59E0B"
          strokeDasharray="5 5"
          label={{ value: "10% target", fill: "#F59E0B", fontSize: 10 }}
        />
        <Bar dataKey="reject_rate" name="Reject Rate" radius={[3, 3, 0, 0]}>
          {data.map((entry, i) => (
            <Cell key={i} fill={REJECT_COLOR(entry.reject_rate)} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
