"use client";

import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
  Legend,
} from "recharts";
import type { LeakageCategory } from "@shared/types/reclaimrx";
import { useRouter } from "next/navigation";

const CATEGORY_COLORS: Record<LeakageCategory, string> = {
  pharmacy_misuse: "#EF4444",
  accumulator: "#F59E0B",
  maximizer: "#F97316",
  three_forty_b_overlap: "#8B5CF6",
  alternative_funding: "#3B82F6",
  prescriber_anomaly: "#10B981",
  patient_anomaly: "#6B7280",
};

const CATEGORY_LABELS: Record<LeakageCategory, string> = {
  pharmacy_misuse: "Pharmacy Misuse",
  accumulator: "Accumulator",
  maximizer: "Maximizer",
  three_forty_b_overlap: "340B Overlap",
  alternative_funding: "Alt. Funding",
  prescriber_anomaly: "Prescriber Anomaly",
  patient_anomaly: "Patient Anomaly",
};

interface DataPoint {
  category: LeakageCategory;
  amount: string;
  count: number;
}

interface Props {
  data: DataPoint[];
}

export function ReclaimRxLeakageCategoryDonut({ data }: Props) {
  const router = useRouter();

  interface ChartItem {
    name: string;
    value: number;
    category: LeakageCategory;
    count: number;
  }

  const chartData: ChartItem[] = data.map((d) => ({
    name: CATEGORY_LABELS[d.category] ?? d.category,
    value: parseFloat(d.amount),
    category: d.category,
    count: d.count,
  }));

  return (
    <ResponsiveContainer width="100%" height={240}>
      <PieChart>
        <Pie
          data={chartData}
          cx="45%"
          cy="50%"
          innerRadius={56}
          outerRadius={88}
          dataKey="value"
          cursor="pointer"
          onClick={(entry: unknown) => {
            const e = entry as ChartItem;
            if (e?.category) {
              router.push(`/reclaimrx/leakage?category=${e.category}`);
            }
          }}
        >
          {chartData.map((entry) => (
            <Cell
              key={entry.category}
              fill={CATEGORY_COLORS[entry.category] ?? "#6B7280"}
            />
          ))}
        </Pie>
        <Tooltip
          formatter={(value: unknown) => {
            const n = value as number;
            return [`$${(n / 1000).toFixed(0)}K`, "Leakage"];
          }}
          contentStyle={{
            background: "#fff",
            border: "1px solid #E8EAF0",
            borderRadius: 8,
            fontSize: 12,
          }}
        />
        <Legend
          layout="vertical"
          align="right"
          verticalAlign="middle"
          formatter={(value: string) => (
            <span style={{ fontSize: 11, color: "#374151" }}>{value}</span>
          )}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}
