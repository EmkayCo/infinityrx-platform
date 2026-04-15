"use client";

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";

interface PdcBucket { bucket: string; patient_count: number; is_adherent: boolean; }

interface Props { data: PdcBucket[]; }

export function AnalyticsPdcHistogram({ data }: Props) {
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#E8EAF0" />
        <XAxis dataKey="bucket" tick={{ fontSize: 11, fill: "#9BA3B5" }} />
        <YAxis tick={{ fontSize: 11, fill: "#9BA3B5" }} />
        <Tooltip
          contentStyle={{ background: "#fff", border: "1px solid #E8EAF0", borderRadius: 8 }}
          formatter={(v: unknown) => [Number(v).toLocaleString(), "Patients"]}
        />
        <Bar dataKey="patient_count" name="Patients" radius={[3, 3, 0, 0]}>
          {data.map((row, i) => (
            <Cell key={i} fill={row.is_adherent ? "#10B981" : row.patient_count > 400 ? "#F59E0B" : "#EF4444"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
