"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import type { GTNTrendPoint } from "@shared/types/reclaimrx";

interface Props {
  data: GTNTrendPoint[];
  onPointClick?: (month: string) => void;
}

function formatGtnPct(value: unknown): string {
  const n = parseFloat(String(value));
  if (isNaN(n)) return "";
  return `${(n * 100).toFixed(1)}%`;
}

export function ReclaimRxGtnTrendLine({ data, onPointClick }: Props) {
  const chartData = data.map((d) => ({
    month: d.month,
    gtn: parseFloat(d.gtn_ratio),
    leakage: parseFloat(d.leakage_amount) / 1000, // display in $K
  }));

  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart
        data={chartData}
        margin={{ top: 4, right: 16, left: 0, bottom: 0 }}
        onClick={(payload) => {
          if (payload?.activeLabel && onPointClick) {
            onPointClick(String(payload.activeLabel));
          }
        }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="var(--ifx-gray-100, #E8EAF0)" />
        <XAxis
          dataKey="month"
          tick={{ fontSize: 11, fill: "var(--ifx-gray-400, #9BA3B5)" }}
          tickFormatter={(v: string) => v.slice(5)}
        />
        <YAxis
          domain={[0.6, 1.0]}
          tickFormatter={formatGtnPct}
          tick={{ fontSize: 11, fill: "var(--ifx-gray-400, #9BA3B5)" }}
        />
        <Tooltip
          formatter={(value: unknown, name: unknown) => {
            if (name === "GTN Ratio") return formatGtnPct(value);
            return `$${(value as number).toFixed(0)}K`;
          }}
          contentStyle={{
            background: "#fff",
            border: "1px solid #E8EAF0",
            borderRadius: 8,
            fontSize: 12,
          }}
        />
        <ReferenceLine y={0.85} stroke="#10B981" strokeDasharray="4 4" label={{ value: "Target", fontSize: 11, fill: "#10B981" }} />
        <Line
          type="monotone"
          dataKey="gtn"
          stroke="#19286B"
          strokeWidth={2.5}
          dot={{ r: 3, fill: "#19286B" }}
          activeDot={{ r: 5, cursor: onPointClick ? "pointer" : "default" }}
          name="GTN Ratio"
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
