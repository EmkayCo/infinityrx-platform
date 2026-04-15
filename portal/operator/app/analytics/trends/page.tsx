"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import { FilterPanel, type FilterField, type FilterValues } from "@/components/ui/filter-panel";
import { ConfigurableDataTable, type Column } from "@/components/ui/configurable-data-table";
import { Skeleton } from "@shared/components/skeleton";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { apiGet, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";

const AnalyticsTrendYoyLine = dynamic(
  () => import("@/components/charts/analytics/trend-yoy-line").then((m) => m.AnalyticsTrendYoyLine),
  { ssr: false, loading: () => <Skeleton className="h-72" /> }
);
const AnalyticsTrendDecompositionWaterfall = dynamic(
  () => import("@/components/charts/analytics/trend-decomposition-waterfall").then((m) => m.AnalyticsTrendDecompositionWaterfall),
  { ssr: false, loading: () => <Skeleton className="h-80" /> }
);

interface TrendsData {
  yoy_spend: { period: string; spend: string; year: number; is_current_year: boolean }[];
  decomposition: {
    period_label: string;
    starting_spend: string;
    utilization_change: string;
    unit_cost_change: string;
    mix_change: string;
    ending_spend: string;
    total_change: string;
    total_change_pct: number;
    components: { label: string; value: string; is_total?: boolean; is_start?: boolean; is_end?: boolean; is_positive?: boolean }[];
  };
  top_movers_increase: { drug_name: string; ndc: string; company_name: string; prior_spend: string; current_spend: string; dollar_change: string; pct_change: number; driver: string }[];
  top_movers_decrease: { drug_name: string; ndc: string; company_name: string; prior_spend: string; current_spend: string; dollar_change: string; pct_change: number; driver: string }[];
}

const FILTERS: FilterField[] = [
  { id: "date_from", label: "Date From", type: "date" },
  { id: "date_to", label: "Date To", type: "date" },
  { id: "drug", label: "Drug / NDC", type: "text" },
  { id: "pharmacy", label: "Pharmacy", type: "text" },
  { id: "state", label: "State", type: "select", options: [
    { value: "", label: "All States" }, { value: "TX", label: "Texas" }, { value: "CA", label: "California" },
  ]},
  { id: "plan", label: "Plan / BIN", type: "text" },
];

const MOVER_COLUMNS_INCREASE: Column<TrendsData["top_movers_increase"][number]>[] = [
  { id: "drug_name", header: "Drug Name", accessor: (r) => r.drug_name, defaultVisible: true, sortable: true },
  { id: "company_name", header: "Company", accessor: (r) => r.company_name, defaultVisible: true },
  { id: "prior_spend", header: "Prior Spend", accessor: (r) => r.prior_spend, format: "currency", defaultVisible: true, align: "right" },
  { id: "current_spend", header: "Current Spend", accessor: (r) => r.current_spend, format: "currency", defaultVisible: true, align: "right" },
  { id: "dollar_change", header: "$ Change", accessor: (r) => r.dollar_change, format: "currency", defaultVisible: true, sortable: true, align: "right",
    cell: (v) => <span className="text-red-600 font-semibold">+{Number(v).toLocaleString("en-US", { style: "currency", currency: "USD" })}</span> },
  { id: "pct_change", header: "% Change", accessor: (r) => r.pct_change, defaultVisible: true, align: "right",
    cell: (v) => <span className="text-red-600">+{Number(v).toFixed(1)}%</span> },
  { id: "driver", header: "Driver", accessor: (r) => r.driver, defaultVisible: true },
];

const MOVER_COLUMNS_DECREASE: Column<TrendsData["top_movers_decrease"][number]>[] = [
  { id: "drug_name", header: "Drug Name", accessor: (r) => r.drug_name, defaultVisible: true, sortable: true },
  { id: "company_name", header: "Company", accessor: (r) => r.company_name, defaultVisible: true },
  { id: "prior_spend", header: "Prior Spend", accessor: (r) => r.prior_spend, format: "currency", defaultVisible: true, align: "right" },
  { id: "current_spend", header: "Current Spend", accessor: (r) => r.current_spend, format: "currency", defaultVisible: true, align: "right" },
  { id: "dollar_change", header: "$ Change", accessor: (r) => r.dollar_change, format: "currency", defaultVisible: true, sortable: true, align: "right",
    cell: (v) => <span className="text-green-600 font-semibold">{Number(v).toLocaleString("en-US", { style: "currency", currency: "USD" })}</span> },
  { id: "pct_change", header: "% Change", accessor: (r) => r.pct_change, defaultVisible: true, align: "right",
    cell: (v) => <span className="text-green-600">{Number(v).toFixed(1)}%</span> },
  { id: "driver", header: "Driver", accessor: (r) => r.driver, defaultVisible: true },
];

export default function TrendAnalysisPage() {
  const [filters, setFilters] = useState<FilterValues>({});

  const { data, isLoading } = useQuery<TrendsData>({
    queryKey: ["analytics-trends-summary", filters],
    queryFn: () => apiGet<TrendsData>(buildUrl(`${API_URLS.dataiq}/api/v1/analytics/trends/summary`)),
    staleTime: 120_000,
  });

  return (
    <div className="flex gap-4">
      <FilterPanel filters={FILTERS} values={filters} onChange={setFilters} onClear={() => setFilters({})} />

      <div className="flex-1 min-w-0 space-y-6">
        <div>
          <span className="text-[11px] font-semibold uppercase tracking-wider text-ifx-navy">Analytics</span>
          <h1 className="mt-1 text-2xl font-bold text-ifx-gray-900">Trend Analysis</h1>
          <p className="mt-1 text-sm text-ifx-gray-400">YoY spend comparison, trend decomposition (utilization + unit cost + mix), and top movers.</p>
        </div>

        {/* YoY Spend Line */}
        <ErrorBoundary>
          <div className="rounded-lg bg-white ifx-card-shadow p-5">
            <h3 className="text-sm font-semibold text-ifx-gray-900 mb-4">Year-over-Year Spend Comparison</h3>
            {isLoading ? <Skeleton className="h-72" /> : data ? (
              <AnalyticsTrendYoyLine data={data.yoy_spend} />
            ) : null}
          </div>
        </ErrorBoundary>

        {/* Trend Decomposition Waterfall */}
        <ErrorBoundary>
          <div className="rounded-lg bg-white ifx-card-shadow p-5">
            <h3 className="text-sm font-semibold text-ifx-gray-900 mb-1">Trend Decomposition Waterfall</h3>
            <p className="text-xs text-ifx-gray-400 mb-4">
              Breaking total spend change into components: utilization + unit cost + mix = total change.
              Answers &ldquo;Why did spend change?&rdquo;
            </p>
            {isLoading ? <Skeleton className="h-80" /> : data ? (
              <AnalyticsTrendDecompositionWaterfall
                components={data.decomposition.components}
                period_label={data.decomposition.period_label}
                total_change_pct={data.decomposition.total_change_pct}
              />
            ) : null}
          </div>
        </ErrorBoundary>

        {/* Top Movers */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="rounded-lg bg-white ifx-card-shadow p-5">
            <h3 className="text-sm font-semibold text-ifx-gray-900 mb-1">Top Cost Increasers</h3>
            <p className="text-xs text-red-500 mb-4">Drugs with largest spend increase period-over-period</p>
            {isLoading ? <Skeleton className="h-48" /> : data ? (
              <ConfigurableDataTable
                tableId="analytics-trends-increasers"
                columns={MOVER_COLUMNS_INCREASE}
                data={data.top_movers_increase}
                searchable
                exportable
              />
            ) : null}
          </div>

          <div className="rounded-lg bg-white ifx-card-shadow p-5">
            <h3 className="text-sm font-semibold text-ifx-gray-900 mb-1">Top Cost Decreasers</h3>
            <p className="text-xs text-green-600 mb-4">Drugs with largest spend decrease period-over-period</p>
            {isLoading ? <Skeleton className="h-48" /> : data ? (
              <ConfigurableDataTable
                tableId="analytics-trends-decreasers"
                columns={MOVER_COLUMNS_DECREASE}
                data={data.top_movers_decrease}
                searchable
                exportable
              />
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
