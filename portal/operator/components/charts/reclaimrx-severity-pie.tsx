"use client";

import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import type { FlagSeverity } from "@shared/types/reclaimrx";

const SEVERITY_COLORS: Record<FlagSeverity, string> = {
  critical: "#EF4444",
  high: "#F97316",
  medium: "#F59E0B",
  low: "#6B7280",
};

interface Props {
  data: { name: string; value: number }[];
}

export function ReclaimRxSeverityPie({ data }: Props) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          innerRadius={50}
          outerRadius={80}
          dataKey="value"
          label={({ name, percent }) =>
            `${name ?? ""} ${Math.round((percent ?? 0) * 100)}%`
          }
          labelLine={false}
        >
          {data.map((entry) => (
            <Cell
              key={entry.name}
              fill={SEVERITY_COLORS[entry.name as FlagSeverity] ?? "#6B7280"}
            />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{
            background: "#1E293B",
            border: "1px solid #334155",
            borderRadius: 8,
          }}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}
