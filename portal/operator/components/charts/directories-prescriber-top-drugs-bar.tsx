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

interface TopDrug {
  drug_name: string;
  claim_count: number;
}

interface Props {
  data: TopDrug[];
}

export function DirectoriesPrescriberTopDrugsBar({ data }: Props) {
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={data} layout="vertical">
        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
        <XAxis type="number" tick={{ fontSize: 11, fill: "#94A3B8" }} />
        <YAxis
          type="category"
          dataKey="drug_name"
          tick={{ fontSize: 10, fill: "#94A3B8" }}
          width={140}
        />
        <Tooltip
          contentStyle={{
            background: "#1E293B",
            border: "1px solid #334155",
            borderRadius: 8,
          }}
        />
        <Bar dataKey="claim_count" fill="#00B4D8" name="Claims" radius={[0, 3, 3, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
