"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import { Download } from "lucide-react";
import { FilterPanel, type FilterField, type FilterValues, type PeriodOption } from "@/components/ui/filter-panel";
import { KpiCardRow } from "@/components/ui/kpi-card-row";
import { ConfigurableDataTable, type Column } from "@/components/ui/configurable-data-table";
import { Skeleton } from "@shared/components/skeleton";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { apiGet, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";

// Lazy-load charts per spec
const AnalyticsClaimsBar = dynamic(
  () => import("@/components/charts/analytics/claims-bar").then((m) => m.AnalyticsClaimsBar),
  { ssr: false, loading: () => <Skeleton className="h-72" /> }
);
const AnalyticsClaimStatusStackedBar = dynamic(
  () => import("@/components/charts/analytics/claim-status-stacked-bar").then((m) => m.AnalyticsClaimStatusStackedBar),
  { ssr: false, loading: () => <Skeleton className="h-72" /> }
);
const AnalyticsOccBar = dynamic(
  () => import("@/components/charts/analytics/occ-bar").then((m) => m.AnalyticsOccBar),
  { ssr: false, loading: () => <Skeleton className="h-60" /> }
);
const AnalyticsRejectCodesBar = dynamic(
  () => import("@/components/charts/analytics/reject-codes-bar").then((m) => m.AnalyticsRejectCodesBar),
  { ssr: false, loading: () => <Skeleton className="h-60" /> }
);

interface ClaimSummaryData {
  kpis: {
    claim_count: number;
    ingredient_cost: string;
    sales_tax: string;
    patient_paid: string;
    dispensing_fee: string;
    paid_claim: string;
    copay_assistance_total: string;
    transaction_fee: string;
  };
  monthly: {
    period: string;
    net_claim_count: number;
    new_enrollments: number;
    benefit_spend: string;
    avg_benefit: string;
    abandonment_rate: number;
    total_pharmacies: number;
    copay_assistance: string;
  }[];
  claim_status: { period: string; paid: number; reversed: number; pending: number; rejected: number }[];
  occ_distribution: { occ: string; count: number; pct: number }[];
  reject_codes: { code: string; count: number; pct: number }[];
}

const FILTERS: FilterField[] = [
  { id: "date_from", label: "Date From", type: "date" },
  { id: "date_to", label: "Date To", type: "date" },
  { id: "drug", label: "Drug / NDC", type: "text", placeholder: "Drug name or NDC" },
  { id: "pharmacy", label: "Pharmacy", type: "text", placeholder: "Name or NPI" },
  { id: "plan", label: "Plan / BIN", type: "text" },
  { id: "group", label: "Group", type: "text" },
  { id: "state", label: "State", type: "select", options: [
    { value: "", label: "All States" },
    { value: "TX", label: "Texas" }, { value: "CA", label: "California" },
    { value: "FL", label: "Florida" }, { value: "NY", label: "New York" },
    { value: "IL", label: "Illinois" },
  ]},
  { id: "status", label: "Claim Status", type: "multi-select", options: [
    { value: "paid", label: "Paid" }, { value: "reversed", label: "Reversed" },
    { value: "pending", label: "Pending" }, { value: "rejected", label: "Rejected" },
  ]},
  { id: "occ", label: "OCC Code", type: "select", options: [
    { value: "", label: "All OCC" }, { value: "00", label: "00 – Not Specified" },
    { value: "01", label: "01 – No Other Coverage" },
  ]},
];

const TABLE_COLUMNS: Column<ClaimSummaryData["monthly"][number]>[] = [
  { id: "period", header: "Period", accessor: (r) => r.period, defaultVisible: true, sortable: true },
  { id: "net_claim_count", header: "Net Claims", accessor: (r) => r.net_claim_count, format: "number", defaultVisible: true, sortable: true, align: "right" },
  { id: "benefit_spend", header: "Total Benefit Spend", accessor: (r) => r.benefit_spend, format: "currency", defaultVisible: true, sortable: true, align: "right" },
  { id: "avg_benefit", header: "Avg Benefit", accessor: (r) => r.avg_benefit, format: "currency", defaultVisible: true, sortable: true, align: "right" },
  { id: "abandonment_rate", header: "Abandonment Rate", accessor: (r) => r.abandonment_rate, defaultVisible: true, align: "right",
    cell: (v) => `${(Number(v) * 100).toFixed(1)}%` },
  { id: "total_pharmacies", header: "Pharmacies", accessor: (r) => r.total_pharmacies, format: "number", defaultVisible: true, align: "right" },
  { id: "copay_assistance", header: "Copay Spend", accessor: (r) => r.copay_assistance, format: "currency", defaultVisible: true, align: "right" },
  { id: "new_enrollments", header: "New Enrollments", accessor: (r) => r.new_enrollments, format: "number", defaultVisible: false, align: "right" },
];

function exportCsv(data: ClaimSummaryData["monthly"]) {
  const headers = ["Period", "Net Claims", "Benefit Spend", "Avg Benefit", "Abandonment Rate", "Pharmacies", "Copay Spend"];
  const rows = data.map((r) => [
    r.period, r.net_claim_count, r.benefit_spend, r.avg_benefit,
    (r.abandonment_rate * 100).toFixed(1) + "%", r.total_pharmacies, r.copay_assistance,
  ]);
  const csv = [headers, ...rows].map((r) => r.join(",")).join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = "claim-summary.csv"; a.click();
  URL.revokeObjectURL(url);
}

export default function ClaimSummaryPage() {
  const [filters, setFilters] = useState<FilterValues>({});
  const [period, setPeriod] = useState<PeriodOption>("monthly");

  const { data, isLoading } = useQuery<ClaimSummaryData>({
    queryKey: ["analytics-claims-summary", filters, period],
    queryFn: () => apiGet<ClaimSummaryData>(buildUrl(`${API_URLS.dataiq}/api/v1/analytics/claims/summary`)),
    staleTime: 120_000,
  });

  const kpiCards = data ? [
    { label: "Claim Count", value: data.kpis.claim_count, format: "number" as const },
    { label: "Ingredient Cost", value: data.kpis.ingredient_cost, format: "currency" as const, accentColor: "var(--ifx-blue)" },
    { label: "Sales Tax", value: data.kpis.sales_tax, format: "currency" as const },
    { label: "Patient Paid", value: data.kpis.patient_paid, format: "currency" as const },
    { label: "Dispensing Fee", value: data.kpis.dispensing_fee, format: "currency" as const },
    { label: "Paid Claim Total", value: data.kpis.paid_claim, format: "currency" as const, accentColor: "#10B981" },
    { label: "Copay Assistance", value: data.kpis.copay_assistance_total, format: "currency" as const, accentColor: "#FF77FF" },
    { label: "Transaction Fee", value: data.kpis.transaction_fee, format: "currency" as const },
  ] : [];

  return (
    <div className="flex gap-4">
      {/* Filter Panel */}
      <FilterPanel
        filters={FILTERS}
        values={filters}
        onChange={setFilters}
        onClear={() => setFilters({})}
        periodToggle
        period={period}
        onPeriodChange={setPeriod}
        collapsible
      />

      {/* Main Content */}
      <div className="flex-1 min-w-0 space-y-6">
        <div>
          <span className="text-[11px] font-semibold uppercase tracking-wider text-ifx-navy">Analytics</span>
          <h1 className="mt-1 text-2xl font-bold text-ifx-gray-900">Claim Summary</h1>
          <p className="mt-1 text-sm text-ifx-gray-400">Power BI-parity claim analytics — period breakdown, status distribution, OCC, and reject codes.</p>
        </div>

        {/* KPI Cards */}
        {isLoading ? (
          <div className="grid grid-cols-2 sm:grid-cols-4 xl:grid-cols-8 gap-3">
            {Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-24" />)}
          </div>
        ) : (
          <KpiCardRow cards={kpiCards} columns={4} />
        )}

        {/* Charts Row 1: Net Claims + New Enrollments */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <ErrorBoundary>
            <div className="rounded-lg bg-white ifx-card-shadow p-5">
              <h3 className="text-sm font-semibold text-ifx-gray-900 mb-4">Net Claim Count &amp; New Enrollments by Period</h3>
              {isLoading ? <Skeleton className="h-72" /> : data ? (
                <AnalyticsClaimsBar
                  data={data.monthly}
                  onBarClick={(period) => console.info("Drill: period", period)}
                />
              ) : null}
            </div>
          </ErrorBoundary>

          <ErrorBoundary>
            <div className="rounded-lg bg-white ifx-card-shadow p-5">
              <h3 className="text-sm font-semibold text-ifx-gray-900 mb-4">Claim Status by Period</h3>
              {isLoading ? <Skeleton className="h-72" /> : data ? (
                <AnalyticsClaimStatusStackedBar data={data.claim_status} />
              ) : null}
            </div>
          </ErrorBoundary>
        </div>

        {/* Charts Row 2: OCC + Reject Codes */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <ErrorBoundary>
            <div className="rounded-lg bg-white ifx-card-shadow p-5">
              <h3 className="text-sm font-semibold text-ifx-gray-900 mb-4">Claims by OCC (Other Coverage Code)</h3>
              {isLoading ? <Skeleton className="h-60" /> : data ? (
                <AnalyticsOccBar data={data.occ_distribution} />
              ) : null}
            </div>
          </ErrorBoundary>

          <ErrorBoundary>
            <div className="rounded-lg bg-white ifx-card-shadow p-5">
              <h3 className="text-sm font-semibold text-ifx-gray-900 mb-4">Top Reject Codes</h3>
              {isLoading ? <Skeleton className="h-60" /> : data ? (
                <AnalyticsRejectCodesBar data={data.reject_codes} />
              ) : null}
            </div>
          </ErrorBoundary>
        </div>

        {/* Summary Table */}
        <div className="rounded-lg bg-white ifx-card-shadow p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-ifx-gray-900">Monthly Breakdown</h3>
            <button
              type="button"
              onClick={() => data && exportCsv(data.monthly)}
              className="flex items-center gap-1.5 rounded-md border border-ifx-gray-100 bg-white px-3 py-1.5 text-xs font-medium text-ifx-gray-700 hover:bg-ifx-gray-50"
            >
              <Download className="h-3.5 w-3.5" />
              Export CSV
            </button>
          </div>
          {isLoading ? <Skeleton className="h-64" /> : data ? (
            <ConfigurableDataTable
              tableId="analytics-claims-monthly"
              columns={TABLE_COLUMNS}
              data={data.monthly}
              searchable
              exportable
            />
          ) : null}
        </div>
      </div>
    </div>
  );
}
