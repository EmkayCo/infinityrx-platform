"use client";

/**
 * Copay Impact Comparison — with-card vs without-card cohort side-by-side.
 * This is the ROI proof chart — the most important chart in the entire portal.
 * Spec: Adherence page, side-by-side bar comparing PDC, persistence, adherence%.
 */
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from "recharts";

interface CohortData {
  with_card: {
    cohort_label: string;
    avg_pdc: number;
    persistence_6mo: number;
    persistence_12mo: number;
    avg_fills_per_patient: number;
    adherent_pct: number;
  };
  without_card: {
    cohort_label: string;
    avg_pdc: number;
    persistence_6mo: number;
    persistence_12mo: number;
    avg_fills_per_patient: number;
    adherent_pct: number;
  };
  pdc_lift: number;
}

interface Props { data: CohortData; }

export function AnalyticsCopayImpactComparison({ data }: Props) {
  const chartData = [
    {
      metric: "PDC",
      with_card: Math.round(data.with_card.avg_pdc * 100),
      without_card: Math.round(data.without_card.avg_pdc * 100),
    },
    {
      metric: "Persistence 6mo",
      with_card: Math.round(data.with_card.persistence_6mo * 100),
      without_card: Math.round(data.without_card.persistence_6mo * 100),
    },
    {
      metric: "Persistence 12mo",
      with_card: Math.round(data.with_card.persistence_12mo * 100),
      without_card: Math.round(data.without_card.persistence_12mo * 100),
    },
    {
      metric: "Adherent %",
      with_card: Math.round(data.with_card.adherent_pct * 100),
      without_card: Math.round(data.without_card.adherent_pct * 100),
    },
  ];

  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <span className="rounded-full bg-ifx-lavender px-3 py-1 text-xs font-semibold text-ifx-navy">
          PDC Lift: +{Math.round(data.pdc_lift * 100)} pp
        </span>
        <span className="text-xs text-ifx-gray-400">
          Patients with copay card show significantly higher adherence and persistence
        </span>
      </div>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={chartData} barGap={6}>
          <CartesianGrid strokeDasharray="3 3" stroke="#E8EAF0" />
          <XAxis dataKey="metric" tick={{ fontSize: 12, fill: "#374151" }} />
          <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: "#9BA3B5" }} tickFormatter={(v: number) => `${v}%`} />
          <Tooltip
            contentStyle={{ background: "#fff", border: "1px solid #E8EAF0", borderRadius: 8 }}
            formatter={(v: unknown) => [`${Number(v)}%`]}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Bar dataKey="with_card" name="With Copay Card" fill="#10B981" radius={[3, 3, 0, 0]} barSize={36} />
          <Bar dataKey="without_card" name="Without Copay Card" fill="#EF4444" radius={[3, 3, 0, 0]} barSize={36} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
