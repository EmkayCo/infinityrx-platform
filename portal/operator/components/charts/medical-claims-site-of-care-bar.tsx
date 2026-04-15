"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  Cell,
} from "recharts";

const POS_COLORS: Record<string, string> = {
  "11": "#10B981",
  "22": "#00B4D8",
  "23": "#EF4444",
  "21": "#F59E0B",
  "24": "#8B5CF6",
  "12": "#6B7280",
};

const POS_DEFAULT_COLOR = "#475569";

interface ChartRow {
  pos: string;
  billed: number;
  paid: number;
  claims: number;
  pos_code: string;
}

interface Props {
  data: ChartRow[];
}

export function MedicalClaimsSiteOfCareBar({ data }: Props) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={data} layout="vertical">
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis
          type="number"
          tick={{ fontSize: 10, fill: "var(--fg-muted)" }}
          tickFormatter={(v: number) => `$${(v / 1000).toFixed(0)}K`}
        />
        <YAxis
          type="category"
          dataKey="pos"
          tick={{ fontSize: 10, fill: "var(--fg-muted)" }}
          width={140}
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
        <Legend />
        <Bar dataKey="billed" name="Billed" fill="#475569" radius={[0, 3, 3, 0]} />
        <Bar dataKey="paid" name="Paid" radius={[0, 3, 3, 0]}>
          {data.map((entry, i) => (
            <Cell key={i} fill={POS_COLORS[entry.pos_code] ?? POS_DEFAULT_COLOR} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
