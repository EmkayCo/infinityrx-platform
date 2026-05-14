import Link from "next/link";
import { ArrowUp, ArrowDown } from "lucide-react";
import { cn } from "@shared/lib/format";
import { formatValue, compactCurrency, type ValueFormat } from "./format-value";

export interface KpiCardProps {
  label: string;
  value: string | number;
  format?: "number" | "currency" | "currency-compact" | "percent" | "raw";
  trend?: {
    value: number;
    direction: "up" | "down";
    label?: string;
  };
  href?: string;
  accentColor?: string;
  icon?: React.ReactNode;
  loading?: boolean;
  className?: string;
  // B11 w2.x — when the BFF reports a field's source is unreachable
  // or not yet aggregated, render "Unavailable" with a muted style
  // instead of the literal value (which would otherwise be 0/empty).
  // Distinguishes "true zero" from "data not yet wired" for the
  // operator. Trend is suppressed when unavailable.
  unavailable?: boolean;
}

function renderValue(value: string | number, format: KpiCardProps["format"]): string {
  if (format === "currency-compact") return compactCurrency(value);
  if (format === "raw" || format === undefined) {
    if (typeof value === "number") return formatValue(value, "number");
    return String(value);
  }
  return formatValue(value, format as ValueFormat);
}

export function KpiCard({
  label,
  value,
  format,
  trend,
  href,
  accentColor = "var(--ifx-blue)",
  icon,
  loading = false,
  className,
  unavailable = false,
}: KpiCardProps) {
  const content = (
    <div
      className={cn(
        "relative flex flex-col gap-1.5 rounded-lg bg-white p-4 ifx-card-shadow transition-all",
        href && "cursor-pointer hover:-translate-y-0.5 ifx-card-shadow-lift",
        className,
      )}
      aria-label={
        unavailable
          ? `${label}: data unavailable (backend source not yet wired)`
          : undefined
      }
    >
      <span
        className="absolute inset-x-0 top-0 h-[3px] rounded-t-lg"
        style={{ backgroundColor: accentColor }}
        aria-hidden="true"
      />
      <div className="flex items-start justify-between gap-2">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-ifx-gray-400">
          {label}
        </span>
        {icon && <span className="text-ifx-gray-400">{icon}</span>}
      </div>
      {loading ? (
        <div className="h-7 w-24 rounded shimmer" />
      ) : unavailable ? (
        <div className="text-[18px] font-semibold leading-tight text-ifx-gray-400 italic">
          Unavailable
        </div>
      ) : (
        <div className="text-[28px] font-bold leading-tight text-ifx-gray-900 tabular-nums">
          {renderValue(value, format)}
        </div>
      )}
      {unavailable && !loading && (
        <span className="text-[10px] uppercase tracking-wide text-ifx-gray-400">
          backend source not yet wired
        </span>
      )}
      {trend && !loading && !unavailable && (
        <div className="flex items-center gap-1 text-xs">
          <span
            className={cn(
              "inline-flex items-center gap-0.5 font-semibold",
              trend.direction === "up" ? "text-ifx-success" : "text-ifx-error",
            )}
          >
            {trend.direction === "up" ? (
              <ArrowUp className="h-3 w-3" />
            ) : (
              <ArrowDown className="h-3 w-3" />
            )}
            {Math.abs(trend.value).toFixed(1)}%
          </span>
          {trend.label && (
            <span className="text-ifx-gray-400">{trend.label}</span>
          )}
        </div>
      )}
    </div>
  );

  if (href) {
    return (
      <Link href={href} className="block">
        {content}
      </Link>
    );
  }
  return content;
}
