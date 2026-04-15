"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import { FilterPanel, type FilterField, type FilterValues } from "@/components/ui/filter-panel";
import { KpiCardRow } from "@/components/ui/kpi-card-row";
import { ConfigurableDataTable, type Column } from "@/components/ui/configurable-data-table";
import { Skeleton } from "@shared/components/skeleton";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { apiGet, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import { StatusBadge } from "@/components/ui/status-badge";

const AnalyticsPdcHistogram = dynamic(
  () => import("@/components/charts/analytics/pdc-histogram").then((m) => m.AnalyticsPdcHistogram),
  { ssr: false, loading: () => <Skeleton className="h-60" /> }
);
const AnalyticsPersistenceCurve = dynamic(
  () => import("@/components/charts/analytics/persistence-curve").then((m) => m.AnalyticsPersistenceCurve),
  { ssr: false, loading: () => <Skeleton className="h-72" /> }
);
const AnalyticsCopayImpactComparison = dynamic(
  () => import("@/components/charts/analytics/copay-impact-comparison").then((m) => m.AnalyticsCopayImpactComparison),
  { ssr: false, loading: () => <Skeleton className="h-72" /> }
);
const AnalyticsAdherenceByPharmacyBar = dynamic(
  () => import("@/components/charts/analytics/adherence-by-pharmacy-bar").then((m) => m.AnalyticsAdherenceByPharmacyBar),
  { ssr: false, loading: () => <Skeleton className="h-72" /> }
);

interface AdherenceData {
  kpis: {
    overall_pdc: number;
    persistence_6mo: number;
    persistence_12mo: number;
    avg_fills_per_patient: number;
  };
  pdc_histogram: { bucket: string; patient_count: number; is_adherent: boolean }[];
  persistence_curve: { month: number; pct_with_card: number; pct_without_card: number }[];
  by_pharmacy: { pharmacy_name: string; npi: string; avg_pdc: number; patient_count: number }[];
  copay_impact: {
    with_card: {
      cohort_label: string; patient_count: number; avg_pdc: number;
      persistence_6mo: number; persistence_12mo: number;
      avg_fills_per_patient: number; avg_copay_paid: string;
      avg_program_spend_per_patient: string; adherent_pct: number;
    };
    without_card: {
      cohort_label: string; patient_count: number; avg_pdc: number;
      persistence_6mo: number; persistence_12mo: number;
      avg_fills_per_patient: number; avg_copay_paid: string;
      avg_program_spend_per_patient: string; adherent_pct: number;
    };
    pdc_lift: number;
    persistence_lift_6mo: number;
    persistence_lift_12mo: number;
    incremental_fills: number;
    roi_per_dollar_spent: string;
  };
  patient_table: {
    patient_id: string; drug_name: string; pdc: number; fills: number;
    first_fill: string; last_fill: string; status: string; has_copay_card: boolean;
  }[];
}

const FILTERS: FilterField[] = [
  { id: "date_from", label: "Date From", type: "date" },
  { id: "date_to", label: "Date To", type: "date" },
  { id: "drug", label: "Drug / NDC", type: "text", placeholder: "Drug name or NDC" },
  { id: "pharmacy", label: "Pharmacy", type: "text" },
  { id: "state", label: "State", type: "select", options: [
    { value: "", label: "All States" }, { value: "TX", label: "Texas" }, { value: "CA", label: "California" },
  ]},
  { id: "pdc_threshold", label: "PDC Threshold", type: "select", options: [
    { value: "", label: "All Patients" }, { value: "0.8", label: "≥ 80% (Adherent)" },
    { value: "0.5", label: "50–79%" }, { value: "0", label: "< 50% (Non-Adherent)" },
  ]},
  { id: "copay_card", label: "Copay Card", type: "select", options: [
    { value: "", label: "All Patients" }, { value: "yes", label: "With Card" }, { value: "no", label: "Without Card" },
  ]},
];

const PATIENT_COLUMNS: Column<AdherenceData["patient_table"][number]>[] = [
  { id: "patient_id", header: "Patient ID", accessor: (r) => r.patient_id, defaultVisible: true },
  { id: "drug_name", header: "Drug", accessor: (r) => r.drug_name, defaultVisible: true, sortable: true },
  { id: "pdc", header: "PDC", accessor: (r) => r.pdc, defaultVisible: true, sortable: true, align: "right",
    cell: (v) => `${Math.round(Number(v) * 100)}%` },
  { id: "fills", header: "Fills", accessor: (r) => r.fills, format: "number", defaultVisible: true, align: "right" },
  { id: "first_fill", header: "First Fill", accessor: (r) => r.first_fill, defaultVisible: true },
  { id: "last_fill", header: "Last Fill", accessor: (r) => r.last_fill, defaultVisible: true },
  { id: "status", header: "Status", accessor: (r) => r.status, defaultVisible: true,
    cell: (v) => <StatusBadge status={String(v)} /> },
  { id: "has_copay_card", header: "Copay Card", accessor: (r) => r.has_copay_card, defaultVisible: true,
    cell: (v) => (
      <span className={`text-xs font-medium ${v ? "text-ifx-success" : "text-ifx-gray-400"}`}>
        {v ? "Yes" : "No"}
      </span>
    )},
];

export default function AdherencePage() {
  const [filters, setFilters] = useState<FilterValues>({});

  const { data, isLoading } = useQuery<AdherenceData>({
    queryKey: ["analytics-adherence-summary", filters],
    queryFn: () => apiGet<AdherenceData>(buildUrl(`${API_URLS.dataiq}/api/v1/analytics/adherence/summary`)),
    staleTime: 120_000,
  });

  const kpiCards = data ? [
    {
      label: "Overall PDC",
      value: `${Math.round(data.kpis.overall_pdc * 100)}%`,
      format: "raw" as const,
      accentColor: data.kpis.overall_pdc >= 0.8 ? "#10B981" : "#F59E0B",
    },
    {
      label: "Persistence — 6 Months",
      value: `${Math.round(data.kpis.persistence_6mo * 100)}%`,
      format: "raw" as const,
    },
    {
      label: "Persistence — 12 Months",
      value: `${Math.round(data.kpis.persistence_12mo * 100)}%`,
      format: "raw" as const,
    },
    {
      label: "Avg Fills / Patient",
      value: data.kpis.avg_fills_per_patient,
      format: "raw" as const,
    },
  ] : [];

  return (
    <div className="flex gap-4">
      <FilterPanel filters={FILTERS} values={filters} onChange={setFilters} onClear={() => setFilters({})} />

      <div className="flex-1 min-w-0 space-y-6">
        <div>
          <span className="text-[11px] font-semibold uppercase tracking-wider text-ifx-navy">Analytics</span>
          <h1 className="mt-1 text-2xl font-bold text-ifx-gray-900">Adherence</h1>
          <p className="mt-1 text-sm text-ifx-gray-400">PDC, persistence curve, adherence by pharmacy, and copay card ROI proof.</p>
        </div>

        {isLoading ? (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24" />)}
          </div>
        ) : (
          <KpiCardRow cards={kpiCards} columns={4} />
        )}

        {/* PDC histogram + Persistence curve */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <ErrorBoundary>
            <div className="rounded-lg bg-white ifx-card-shadow p-5">
              <h3 className="text-sm font-semibold text-ifx-gray-900 mb-4">PDC Distribution — Patient Population</h3>
              {isLoading ? <Skeleton className="h-60" /> : data ? (
                <AnalyticsPdcHistogram data={data.pdc_histogram} />
              ) : null}
            </div>
          </ErrorBoundary>

          <ErrorBoundary>
            <div className="rounded-lg bg-white ifx-card-shadow p-5">
              <h3 className="text-sm font-semibold text-ifx-gray-900 mb-4">Persistence Curve (Kaplan-Meier Style)</h3>
              {isLoading ? <Skeleton className="h-72" /> : data ? (
                <AnalyticsPersistenceCurve data={data.persistence_curve} />
              ) : null}
            </div>
          </ErrorBoundary>
        </div>

        {/* Adherence by pharmacy */}
        <ErrorBoundary>
          <div className="rounded-lg bg-white ifx-card-shadow p-5">
            <h3 className="text-sm font-semibold text-ifx-gray-900 mb-1">Adherence by Pharmacy (Avg PDC)</h3>
            <p className="text-xs text-ifx-gray-400 mb-4">Yellow reference line = 80% PDC threshold (CMS standard)</p>
            {isLoading ? <Skeleton className="h-72" /> : data ? (
              <AnalyticsAdherenceByPharmacyBar data={data.by_pharmacy} />
            ) : null}
          </div>
        </ErrorBoundary>

        {/* Copay Impact Comparison — THE ROI PROOF CHART */}
        <ErrorBoundary>
          <div className="rounded-lg bg-white ifx-card-shadow p-5 border-l-4 border-ifx-pink">
            <div className="flex items-start justify-between mb-2">
              <div>
                <h3 className="text-sm font-semibold text-ifx-gray-900">
                  Copay Card Impact — With Card vs. Without Card
                </h3>
                <p className="text-xs text-ifx-gray-400 mt-0.5">
                  The ROI proof chart: demonstrates adherence improvement from copay assistance program
                </p>
              </div>
              {data && (
                <div className="text-right">
                  <div className="text-xs font-semibold text-ifx-gray-400 uppercase tracking-wide">ROI per $ Spent</div>
                  <div className="text-2xl font-bold text-ifx-navy">${data.copay_impact.roi_per_dollar_spent}</div>
                </div>
              )}
            </div>

            {/* Cohort comparison cards */}
            {data && (
              <div className="mb-4 grid grid-cols-2 gap-4">
                {[data.copay_impact.with_card, data.copay_impact.without_card].map((cohort, i) => (
                  <div
                    key={i}
                    className={`rounded-lg p-3 ${i === 0 ? "bg-green-50 border border-green-200" : "bg-red-50 border border-red-200"}`}
                  >
                    <div className={`text-xs font-bold uppercase tracking-wide mb-2 ${i === 0 ? "text-green-700" : "text-red-700"}`}>
                      {cohort.cohort_label}
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div><span className="text-ifx-gray-400">Patients</span><br /><strong>{cohort.patient_count.toLocaleString()}</strong></div>
                      <div><span className="text-ifx-gray-400">Avg PDC</span><br /><strong>{Math.round(cohort.avg_pdc * 100)}%</strong></div>
                      <div><span className="text-ifx-gray-400">Persistence 6mo</span><br /><strong>{Math.round(cohort.persistence_6mo * 100)}%</strong></div>
                      <div><span className="text-ifx-gray-400">Avg Fills</span><br /><strong>{cohort.avg_fills_per_patient}</strong></div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {isLoading ? <Skeleton className="h-72" /> : data ? (
              <AnalyticsCopayImpactComparison data={data.copay_impact} />
            ) : null}
          </div>
        </ErrorBoundary>

        {/* Patient-level table */}
        <div className="rounded-lg bg-white ifx-card-shadow p-5">
          <h3 className="text-sm font-semibold text-ifx-gray-900 mb-4">Patient-Level Adherence</h3>
          {isLoading ? <Skeleton className="h-64" /> : data ? (
            <ConfigurableDataTable
              tableId="analytics-adherence-patients"
              columns={PATIENT_COLUMNS}
              data={data.patient_table}
              searchable
              exportable
            />
          ) : null}
        </div>
      </div>
    </div>
  );
}
