import {
  ResponsiveContainer,
  LineChart as RechartsLineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";

export interface LineChartProps<T extends Record<string, unknown>> {
  data: T[];
  xKey: keyof T & string;
  yKey: keyof T & string;
  title?: string;
  className?: string;
}

/**
 * Thin recharts wrapper. Enforces a consistent chart shape across portals.
 * For complex multi-line charts, compose directly from recharts primitives —
 * this component handles the single-line 80% case.
 */
export function LineChart<T extends Record<string, unknown>>({
  data,
  xKey,
  yKey,
  title,
  className,
}: LineChartProps<T>) {
  return (
    <div className={["irx-line-chart", className].filter(Boolean).join(" ")}>
      {title != null && <p className="irx-line-chart__title">{title}</p>}
      <ResponsiveContainer width="100%" height={200}>
        <RechartsLineChart data={data as object[]}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey={xKey} />
          <YAxis />
          <Tooltip />
          <Line type="monotone" dataKey={yKey} dot={false} />
        </RechartsLineChart>
      </ResponsiveContainer>
    </div>
  );
}
