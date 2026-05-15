export interface KPICardProps {
  label: string;
  value: string | number;
  delta?: string;
  className?: string;
}

/**
 * Simple KPI metric display: label + formatted value + optional delta badge.
 * No recharts dependency — pure CSS layout. Use LineChart for trend visualization.
 */
export function KPICard({ label, value, delta, className }: KPICardProps) {
  return (
    <div className={["irx-kpi-card", className].filter(Boolean).join(" ")}>
      <p className="irx-kpi-card__label">{label}</p>
      <p className="irx-kpi-card__value">{value}</p>
      {delta != null && (
        <span className="irx-kpi-card__delta">{delta}</span>
      )}
    </div>
  );
}
