"use client";

import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import type { GenericBrandBreakdown } from "@shared/types/analytics";

interface Props {
  breakdown: GenericBrandBreakdown;
}

export function AnalyticsDrugTrendBrandGenericPie({ breakdown }: Props) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <PieChart>
        <Pie
          data={[
            { name: "Brand", value: breakdown.brand_pct },
            { name: "Generic", value: breakdown.generic_pct },
          ]}
          cx="50%"
          cy="50%"
          innerRadius={50}
          outerRadius={80}
          dataKey="value"
          label={(props: { name?: string; value?: number }) =>
            `${props.name ?? ""}: ${Number(props.value ?? 0).toFixed(1)}%`
          }
        >
          <Cell fill="#8B5CF6" />
          <Cell fill="#10B981" />
        </Pie>
        <Tooltip
          formatter={(v) => [`${Number(v).toFixed(1)}%`]}
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
