"use client";

/**
 * Trend Decomposition Waterfall Chart.
 * Shows how utilization, unit cost, and mix changes combine into total spend change.
 * Uses Recharts ComposedChart with a custom "floating bar" pattern.
 */
import { ComposedChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from "recharts";

interface DecompositionComponent {
  label: string;
  value: string;
  is_total?: boolean;
  is_start?: boolean;
  is_end?: boolean;
  is_positive?: boolean;
}

interface Props {
  components: DecompositionComponent[];
  period_label: string;
  total_change_pct: number;
}

export function AnalyticsTrendDecompositionWaterfall({ components, period_label, total_change_pct }: Props) {
  // Build waterfall data: each bar has a "base" (invisible) and a "value" bar
  let running = 0;
  const chartData = components.map((c) => {
    const rawValue = parseFloat(c.value);
    if (c.is_start) {
      running = rawValue;
      return { label: c.label, base: 0, value: rawValue, raw: rawValue, is_total: true };
    }
    if (c.is_end) {
      return { label: c.label, base: 0, value: rawValue, raw: rawValue, is_total: true };
    }
    const base = rawValue < 0 ? running + rawValue : running;
    const absValue = Math.abs(rawValue);
    running += rawValue;
    return { label: c.label, base, value: absValue, raw: rawValue, is_total: false };
  });

  function barColor(d: typeof chartData[0]): string {
    if (d.is_total) return "#19286B";
    return d.raw >= 0 ? "#EF4444" : "#10B981";
  }

  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <span className="text-xs font-semibold text-ifx-gray-700">{period_label}</span>
        <span className={`rounded-full px-2 py-0.5 text-xs font-bold ${total_change_pct > 0 ? "bg-red-50 text-red-600" : "bg-green-50 text-green-700"}`}>
          {total_change_pct > 0 ? "+" : ""}{total_change_pct.toFixed(1)}% total change
        </span>
      </div>
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#E8EAF0" />
          <XAxis dataKey="label" tick={{ fontSize: 10, fill: "#374151" }} />
          <YAxis
            tick={{ fontSize: 11, fill: "#9BA3B5" }}
            tickFormatter={(v: number) => `$${(v / 1_000_000).toFixed(1)}M`}
          />
          <Tooltip
            contentStyle={{ background: "#fff", border: "1px solid #E8EAF0", borderRadius: 8 }}
            formatter={(v: unknown, name: unknown) => {
              if (name === "base") return null;
              return [`$${(Number(v) / 1000).toFixed(0)}K`];
            }}
          />
          {/* Invisible base bar */}
          <Bar dataKey="base" stackId="a" fill="transparent" />
          {/* Visible value bar */}
          <Bar dataKey="value" stackId="a" name="Amount" radius={[3, 3, 0, 0]}>
            {chartData.map((d, i) => (
              <Cell key={i} fill={barColor(d)} />
            ))}
          </Bar>
        </ComposedChart>
      </ResponsiveContainer>
      <div className="mt-3 flex gap-4 text-xs">
        <span className="flex items-center gap-1">
          <span className="inline-block h-3 w-3 rounded-sm bg-ifx-navy" />
          Total / Base
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-3 w-3 rounded-sm bg-red-500" />
          Cost Increase
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-3 w-3 rounded-sm bg-green-500" />
          Cost Decrease
        </span>
      </div>
    </div>
  );
}
