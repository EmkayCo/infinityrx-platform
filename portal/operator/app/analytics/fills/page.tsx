"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import { FilterPanel, type FilterField, type FilterValues, type PeriodOption } from "@/components/ui/filter-panel";
import { KpiCardRow } from "@/components/ui/kpi-card-row";
import { ConfigurableDataTable, type Column } from "@/components/ui/configurable-data-table";
import { Skeleton } from "@shared/components/skeleton";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { apiGet, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";

const AnalyticsFillsStackedBar = dynamic(
  () => import("@/components/charts/analytics/fills-stacked-bar").then((m) => m.AnalyticsFillsStackedBar),
  { ssr: false, loading: () => <Skeleton className="h-72" /> }
);
const AnalyticsPharmacyTypePie = dynamic(
  () => import("@/components/charts/analytics/pharmacy-type-pie").then((m) => m.AnalyticsPharmacyTypePie),
  { ssr: false, loading: () => <Skeleton className="h-60" /> }
);
const AnalyticsChainFillsBar = dynamic(
  () => import("@/components/charts/analytics/chain-fills-bar").then((m) => m.AnalyticsChainFillsBar),
  { ssr: false, loading: () => <Skeleton className="h-72" /> }
);
const AnalyticsDaysSupplyBar = dynamic(
  () => import("@/components/charts/analytics/days-supply-bar").then((m) => m.AnalyticsDaysSupplyBar),
  { ssr: false, loading: () => <Skeleton className="h-52" /> }
);
const AnalyticsNbrxTrendLine = dynamic(
  () => import("@/components/charts/analytics/nbrx-trend-line").then((m) => m.AnalyticsNbrxTrendLine),
  { ssr: false, loading: () => <Skeleton className="h-60" /> }
);

interface FillsData {
  kpis: {
    total_fills: number;
    new_starts: number;
    refills: number;
    avg_fills_per_patient: number;
    avg_days_supply: number;
  };
  monthly: { period: string; total_fills: number; new_starts: number; refills: number }[];
  by_drug: {
    drug_name: string; ndc: string; company_name: string;
    net_fills: number; new_starts: number; refills: number;
    avg_quantity: number; avg_days_supply: number; total_spend: string;
  }[];
  by_pharmacy_type: { type: string; fills: number; pct: number }[];
  by_chain: { chain: string; fills: number }[];
  days_supply: { days: string; fills: number }[];
  nbrx_trend: { period: string; nbrx: number; trx: number }[];
}

const FILTERS: FilterField[] = [
  { id: "date_from", label: "Date From", type: "date" },
  { id: "date_to", label: "Date To", type: "date" },
  { id: "drug", label: "Drug / NDC", type: "text", placeholder: "Drug name or NDC" },
  { id: "pharmacy", label: "Pharmacy", type: "text", placeholder: "Name or NPI" },
  { id: "pharmacy_type", label: "Pharmacy Type", type: "select", options: [
    { value: "", label: "All Types" }, { value: "chain", label: "Retail – Chain" },
    { value: "independent", label: "Retail – Independent" }, { value: "mail", label: "Mail Order" },
    { value: "specialty", label: "Specialty" }, { value: "340b", label: "340B" },
  ]},
  { id: "state", label: "State", type: "select", options: [
    { value: "", label: "All States" }, { value: "TX", label: "Texas" }, { value: "CA", label: "California" },
  ]},
  { id: "fill_type", label: "Fill Type", type: "select", options: [
    { value: "", label: "All Fills" }, { value: "new", label: "New Starts" }, { value: "refill", label: "Refills" },
  ]},
  { id: "days_supply", label: "Days Supply", type: "select", options: [
    { value: "", label: "All" }, { value: "30", label: "30-day" }, { value: "60", label: "60-day" }, { value: "90", label: "90-day" },
  ]},
];

const DRUG_COLUMNS: Column<FillsData["by_drug"][number]>[] = [
  { id: "drug_name", header: "Drug Name", accessor: (r) => r.drug_name, defaultVisible: true, sortable: true },
  { id: "ndc", header: "NDC", accessor: (r) => r.ndc, defaultVisible: true },
  { id: "company_name", header: "Company", accessor: (r) => r.company_name, defaultVisible: true },
  { id: "net_fills", header: "Net Fills", accessor: (r) => r.net_fills, format: "number", defaultVisible: true, sortable: true, align: "right" },
  { id: "new_starts", header: "New Starts", accessor: (r) => r.new_starts, format: "number", defaultVisible: true, sortable: true, align: "right" },
  { id: "refills", header: "Refills", accessor: (r) => r.refills, format: "number", defaultVisible: true, sortable: true, align: "right" },
  { id: "avg_quantity", header: "Avg Qty", accessor: (r) => r.avg_quantity, defaultVisible: true, align: "right" },
  { id: "avg_days_supply", header: "Avg Days Supply", accessor: (r) => r.avg_days_supply, defaultVisible: true, align: "right" },
  { id: "total_spend", header: "Total Spend", accessor: (r) => r.total_spend, format: "currency", defaultVisible: true, sortable: true, align: "right" },
];

export default function FillPerformancePage() {
  const [filters, setFilters] = useState<FilterValues>({});
  const [period, setPeriod] = useState<PeriodOption>("monthly");

  const { data, isLoading } = useQuery<FillsData>({
    queryKey: ["analytics-fills-summary", filters, period],
    queryFn: () => apiGet<FillsData>(buildUrl(`${API_URLS.dataiq}/api/v1/analytics/fills/summary`)),
    staleTime: 120_000,
  });

  const kpiCards = data ? [
    { label: "Total Fills", value: data.kpis.total_fills, format: "number" as const },
    { label: "NBRx (New Starts)", value: data.kpis.new_starts, format: "number" as const, accentColor: "#FF77FF" },
    { label: "Refills", value: data.kpis.refills, format: "number" as const },
    { label: "Avg Fills / Patient", value: data.kpis.avg_fills_per_patient, format: "raw" as const },
    { label: "Avg Days Supply", value: data.kpis.avg_days_supply, format: "number" as const },
  ] : [];

  return (
    <div className="flex gap-4">
      <FilterPanel
        filters={FILTERS}
        values={filters}
        onChange={setFilters}
        onClear={() => setFilters({})}
        periodToggle
        period={period}
        onPeriodChange={setPeriod}
      />

      <div className="flex-1 min-w-0 space-y-6">
        <div>
          <span className="text-[11px] font-semibold uppercase tracking-wider text-ifx-navy">Analytics</span>
          <h1 className="mt-1 text-2xl font-bold text-ifx-gray-900">Fill Performance</h1>
          <p className="mt-1 text-sm text-ifx-gray-400">NBRx, refills, pharmacy type, chain fills, days supply, and trend analysis.</p>
        </div>

        {isLoading ? (
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
            {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-24" />)}
          </div>
        ) : (
          <KpiCardRow cards={kpiCards} columns={5} />
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <ErrorBoundary>
            <div className="rounded-lg bg-white ifx-card-shadow p-5">
              <h3 className="text-sm font-semibold text-ifx-gray-900 mb-4">Fills by Period (New vs Refill)</h3>
              {isLoading ? <Skeleton className="h-72" /> : data ? (
                <AnalyticsFillsStackedBar data={data.monthly} />
              ) : null}
            </div>
          </ErrorBoundary>

          <ErrorBoundary>
            <div className="rounded-lg bg-white ifx-card-shadow p-5">
              <h3 className="text-sm font-semibold text-ifx-gray-900 mb-4">Fills by Pharmacy Type</h3>
              {isLoading ? <Skeleton className="h-60" /> : data ? (
                <AnalyticsPharmacyTypePie data={data.by_pharmacy_type} />
              ) : null}
            </div>
          </ErrorBoundary>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <ErrorBoundary>
            <div className="rounded-lg bg-white ifx-card-shadow p-5">
              <h3 className="text-sm font-semibold text-ifx-gray-900 mb-4">Fills by Chain (Top 10)</h3>
              {isLoading ? <Skeleton className="h-72" /> : data ? (
                <AnalyticsChainFillsBar data={data.by_chain} />
              ) : null}
            </div>
          </ErrorBoundary>

          <ErrorBoundary>
            <div className="rounded-lg bg-white ifx-card-shadow p-5">
              <h3 className="text-sm font-semibold text-ifx-gray-900 mb-4">Days Supply Distribution</h3>
              {isLoading ? <Skeleton className="h-52" /> : data ? (
                <AnalyticsDaysSupplyBar data={data.days_supply} />
              ) : null}
            </div>
          </ErrorBoundary>
        </div>

        <ErrorBoundary>
          <div className="rounded-lg bg-white ifx-card-shadow p-5">
            <h3 className="text-sm font-semibold text-ifx-gray-900 mb-4">NBRx Trend (New-to-Brand vs Total Rx)</h3>
            {isLoading ? <Skeleton className="h-60" /> : data ? (
              <AnalyticsNbrxTrendLine data={data.nbrx_trend} />
            ) : null}
          </div>
        </ErrorBoundary>

        <div className="rounded-lg bg-white ifx-card-shadow p-5">
          <h3 className="text-sm font-semibold text-ifx-gray-900 mb-4">Drug-Level Fill Detail</h3>
          {isLoading ? <Skeleton className="h-64" /> : data ? (
            <ConfigurableDataTable
              tableId="analytics-fills-by-drug"
              columns={DRUG_COLUMNS}
              data={data.by_drug}
              searchable
              exportable
            />
          ) : null}
        </div>
      </div>
    </div>
  );
}
