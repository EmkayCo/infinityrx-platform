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

interface RejectRateRow {
  name: string;
  reject_rate: number;
  mac_ratio: number;
  tier: string;
}

interface Props {
  data: RejectRateRow[];
}

export function AnalyticsNetworkMacRatioBar({ data }: Props) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
        <XAxis dataKey="name" tick={{ fontSize: 10, fill: "#94A3B8" }} />
        <YAxis
          domain={[0, 1.5]}
          tick={{ fontSize: 10, fill: "#94A3B8" }}
          tickFormatter={(v: number) => `${Number(v).toFixed(1)}x`}
        />
        <Tooltip
          formatter={(v) => [`${Number(v).toFixed(2)}x`, "MAC Ratio"]}
          contentStyle={{
            background: "#1E293B",
            border: "1px solid #334155",
            borderRadius: 8,
          }}
        />
        <ReferenceLine
          y={1.0}
          stroke="#10B981"
          strokeDasharray="5 5"
          label={{ value: "1.0x parity", fill: "#10B981", fontSize: 10 }}
        />
        <Bar dataKey="mac_ratio" name="MAC Ratio" fill="#00B4D8" radius={[3, 3, 0, 0]}>
          {data.map((entry, i) => (
            <Cell
              key={i}
              fill={
                entry.mac_ratio >= 1.0
                  ? "#10B981"
                  : entry.mac_ratio >= 0.9
                  ? "#F59E0B"
                  : "#EF4444"
              }
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
