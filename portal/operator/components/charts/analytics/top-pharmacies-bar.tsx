"use client";

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

interface PharmacyRow { pharmacy_name: string; net_claims: number; npi?: string; }

interface Props { data: PharmacyRow[]; onBarClick?: (pharmacy: PharmacyRow) => void; }

export function AnalyticsTopPharmaciesBar({ data, onBarClick }: Props) {
  function handleClick(event: Record<string, unknown>) {
    if (event?.activePayload && Array.isArray(event.activePayload) && event.activePayload[0] && onBarClick) {
      const payload = (event.activePayload[0] as Record<string, unknown>).payload;
      if (payload) onBarClick(payload as PharmacyRow);
    }
  }

  return (
    <ResponsiveContainer width="100%" height={380}>
      <BarChart
        data={data.slice(0, 20)}
        layout="vertical"
        onClick={handleClick}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="#E8EAF0" horizontal={false} />
        <XAxis type="number" tick={{ fontSize: 11, fill: "#9BA3B5" }} />
        <YAxis dataKey="pharmacy_name" type="category" width={180} tick={{ fontSize: 10, fill: "#374151" }} />
        <Tooltip
          contentStyle={{ background: "#fff", border: "1px solid #E8EAF0", borderRadius: 8 }}
          formatter={(v: unknown) => [Number(v).toLocaleString(), "Claims"]}
        />
        <Bar dataKey="net_claims" name="Net Claims" fill="#324AB2" radius={[0, 3, 3, 0]} cursor="pointer" />
      </BarChart>
    </ResponsiveContainer>
  );
}
