"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

const TOP_DRUG_COLORS = [
  "#00B4D8",
  "#8B5CF6",
  "#10B981",
  "#F59E0B",
  "#EF4444",
  "#EC4899",
  "#14B8A6",
  "#F97316",
];

interface TopDrug {
  drug_name: string;
  ndc: string;
  total_spend: string;
  claim_count: number;
  category: string;
}

interface Props {
  data: TopDrug[];
}

export function AnalyticsDrugTrendTopDrugsBar({ data }: Props) {
  return (
    <ResponsiveContainer width="100%" height={400}>
      <BarChart
        data={data.map((d) => ({ ...d, spend_num: parseFloat(d.total_spend) }))}
        layout="vertical"
      >
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis
          type="number"
          tick={{ fontSize: 10, fill: "var(--fg-muted)" }}
          tickFormatter={(v: number) => `$${(v / 1000).toFixed(0)}K`}
        />
        <YAxis
          type="category"
          dataKey="drug_name"
          tick={{ fontSize: 10, fill: "var(--fg-muted)" }}
          width={160}
        />
        <Tooltip
          formatter={(v) => [
            `$${Number(v).toLocaleString("en-US", { minimumFractionDigits: 2 })}`,
          ]}
          contentStyle={{
            background: "var(--bg-card-alt)", color: "var(--fg)",
            border: "1px solid var(--border)",
            borderRadius: 8,
          }}
        />
        <Bar dataKey="spend_num" name="Total Spend" radius={[0, 3, 3, 0]}>
          {data.map((_, i) => (
            <Cell key={i} fill={TOP_DRUG_COLORS[i % TOP_DRUG_COLORS.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
