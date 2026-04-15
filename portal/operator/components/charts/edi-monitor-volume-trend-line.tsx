"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";

interface VolumeTrendPoint {
  date: string;
  inbound: number;
  outbound: number;
}

interface Props {
  data: VolumeTrendPoint[];
}

export function EdiMonitorVolumeTrendLine({ data }: Props) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 10, fill: "var(--fg-muted)" }}
          tickFormatter={(v: string) => v.slice(5)}
        />
        <YAxis tick={{ fontSize: 11, fill: "var(--fg-muted)" }} />
        <Tooltip
          contentStyle={{
            background: "var(--bg-card-alt)", color: "var(--fg)",
            border: "1px solid var(--border)",
            borderRadius: 8,
          }}
        />
        <Legend />
        <Line
          type="monotone"
          dataKey="inbound"
          stroke="#00B4D8"
          strokeWidth={2}
          dot={false}
          name="Inbound"
        />
        <Line
          type="monotone"
          dataKey="outbound"
          stroke="#F59E0B"
          strokeWidth={2}
          dot={false}
          name="Outbound"
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
