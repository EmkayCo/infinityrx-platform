"use client";

import {
  RadialBarChart,
  RadialBar,
  ResponsiveContainer,
} from "recharts";

interface GaugeRow {
  value: number;
  fill: string;
}

interface Props {
  data: GaugeRow[];
}

export function AnalyticsDataQualityGauge({ data }: Props) {
  return (
    <ResponsiveContainer width={180} height={180}>
      <RadialBarChart
        cx="50%"
        cy="50%"
        innerRadius="60%"
        outerRadius="100%"
        startAngle={90}
        endAngle={-270}
        data={data}
      >
        <RadialBar
          dataKey="value"
          cornerRadius={10}
          background={{ fill: "#1B3A5C" }}
        />
      </RadialBarChart>
    </ResponsiveContainer>
  );
}
