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
import { useRouter } from "next/navigation";

interface ProgramLeakage {
  program_name: string;
  amount: string;
}

interface Props {
  data: ProgramLeakage[];
}

export function ReclaimRxLeakageByProgramBar({ data }: Props) {
  const router = useRouter();

  const chartData = data
    .map((d) => ({
      name: d.program_name.length > 20 ? d.program_name.slice(0, 18) + "…" : d.program_name,
      fullName: d.program_name,
      value: parseFloat(d.amount),
    }))
    .sort((a, b) => b.value - a.value);

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart
        layout="vertical"
        data={chartData}
        margin={{ top: 4, right: 24, left: 8, bottom: 0 }}
        onClick={(payload) => {
          if (payload?.activeLabel) {
            router.push(`/reclaimrx/leakage?program=${encodeURIComponent(String(payload.activeLabel))}`);
          }
        }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="var(--ifx-gray-100, #E8EAF0)" horizontal={false} />
        <XAxis
          type="number"
          tickFormatter={(v: number) => `$${(v / 1000).toFixed(0)}K`}
          tick={{ fontSize: 11, fill: "#9BA3B5" }}
        />
        <YAxis
          type="category"
          dataKey="name"
          width={120}
          tick={{ fontSize: 11, fill: "#374151" }}
        />
        <Tooltip
          formatter={(value: unknown) => [`$${((value as number) / 1000).toFixed(1)}K`, "Leakage"]}
          contentStyle={{
            background: "#fff",
            border: "1px solid #E8EAF0",
            borderRadius: 8,
            fontSize: 12,
          }}
        />
        <Bar dataKey="value" fill="#324AB2" radius={[0, 4, 4, 0]} cursor="pointer" />
      </BarChart>
    </ResponsiveContainer>
  );
}
