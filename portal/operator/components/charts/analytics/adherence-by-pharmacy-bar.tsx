"use client";

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, Cell } from "recharts";

interface PharmacyAdherence { pharmacy_name: string; avg_pdc: number; patient_count: number; }

interface Props { data: PharmacyAdherence[]; }

export function AnalyticsAdherenceByPharmacyBar({ data }: Props) {
  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={data} layout="vertical">
        <CartesianGrid strokeDasharray="3 3" stroke="#E8EAF0" horizontal={false} />
        <XAxis
          type="number"
          domain={[0, 1]}
          tick={{ fontSize: 11, fill: "#9BA3B5" }}
          tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
        />
        <YAxis dataKey="pharmacy_name" type="category" width={180} tick={{ fontSize: 11, fill: "#374151" }} />
        <Tooltip
          contentStyle={{ background: "#fff", border: "1px solid #E8EAF0", borderRadius: 8 }}
          formatter={(v: unknown) => [`${Math.round(Number(v) * 100)}%`, "Avg PDC"]}
        />
        <ReferenceLine x={0.8} stroke="#F59E0B" strokeDasharray="4 4" />
        <Bar dataKey="avg_pdc" name="Avg PDC" radius={[0, 3, 3, 0]}>
          {data.map((row, i) => (
            <Cell key={i} fill={row.avg_pdc >= 0.8 ? "#10B981" : row.avg_pdc >= 0.65 ? "#F59E0B" : "#EF4444"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
