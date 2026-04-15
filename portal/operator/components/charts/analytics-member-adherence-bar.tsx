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
} from "recharts";
import type { MemberAdherence } from "@shared/types/analytics";

const ADHERENCE_COLOR = (pdc: number, threshold: number) => {
  if (pdc >= threshold) return "#10B981";
  if (pdc >= threshold - 10) return "#F59E0B";
  return "#EF4444";
};

interface ChartRow {
  drug_class: string;
  PDC: number;
  threshold: number;
  members: number;
}

interface Props {
  data: ChartRow[];
  adherence: MemberAdherence[];
}

export function AnalyticsMemberAdherenceBar({ data, adherence }: Props) {
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis dataKey="drug_class" tick={{ fontSize: 10, fill: "var(--fg-muted)" }} />
        <YAxis
          domain={[0, 100]}
          tick={{ fontSize: 11, fill: "var(--fg-muted)" }}
          tickFormatter={(v: number) => `${Number(v)}%`}
        />
        <Tooltip
          formatter={(v) => [`${Number(v).toFixed(1)}%`]}
          contentStyle={{
            background: "var(--bg-card-alt)", color: "var(--fg)",
            border: "1px solid var(--border)",
            borderRadius: 8,
          }}
        />
        <ReferenceLine
          y={80}
          stroke="#F59E0B"
          strokeDasharray="5 5"
          label={{ value: "CMS 80%", fill: "#F59E0B", fontSize: 10 }}
        />
        <Bar dataKey="PDC" name="PDC Score" radius={[3, 3, 0, 0]}>
          {adherence.map((a, i) => (
            <rect key={i} fill={ADHERENCE_COLOR(a.pdc_score, a.cms_threshold)} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
