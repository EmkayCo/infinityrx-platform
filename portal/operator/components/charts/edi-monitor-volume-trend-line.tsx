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
        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 10, fill: "#94A3B8" }}
          tickFormatter={(v: string) => v.slice(5)}
        />
        <YAxis tick={{ fontSize: 11, fill: "#94A3B8" }} />
        <Tooltip
          contentStyle={{
            background: "#1E293B",
            border: "1px solid #334155",
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
