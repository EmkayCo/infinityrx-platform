"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { FilterPanel, type FilterField, type FilterValues } from "@/components/ui/filter-panel";
import { KpiCardRow } from "@/components/ui/kpi-card-row";
import { ConfigurableDataTable, type Column } from "@/components/ui/configurable-data-table";
import { Skeleton } from "@shared/components/skeleton";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { apiGet, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";

const AnalyticsStateChoropleth = dynamic(
  () => import("@/components/charts/analytics/state-choropleth").then((m) => m.AnalyticsStateChoropleth),
  { ssr: false, loading: () => <Skeleton className="h-72" /> }
);
const AnalyticsTopPharmaciesBar = dynamic(
  () => import("@/components/charts/analytics/top-pharmacies-bar").then((m) => m.AnalyticsTopPharmaciesBar),
  { ssr: false, loading: () => <Skeleton className="h-96" /> }
);
const AnalyticsPharmacyTypePie = dynamic(
  () => import("@/components/charts/analytics/pharmacy-type-pie").then((m) => m.AnalyticsPharmacyTypePie),
  { ssr: false, loading: () => <Skeleton className="h-60" /> }
);

interface PharmaciesData {
  kpis: {
    total_pharmacies: number;
    avg_claims_per_pharmacy: number;
    avg_benefit_per_pharmacy: string;
    total_spend: string;
  };
  by_state: { state_abbr: string; state_name: string; claim_count: number; spend: string; pharmacy_count: number; avg_benefit: string; abandonment_rate: number }[];
  top_20: {
    pharmacy_name: string; npi: string; ncpdp: string; state: string;
    net_claims: number; pct_covered: number; total_spend: string;
    avg_benefit: string; abandonment_rate: number; risk_score: number; pharmacy_type: string;
  }[];
  type_distribution: { type: string; count: number; claim_share: number }[];
}

const FILTERS: FilterField[] = [
  { id: "date_from", label: "Date From", type: "date" },
  { id: "date_to", label: "Date To", type: "date" },
  { id: "drug", label: "Drug / NDC", type: "text" },
  { id: "state", label: "State", type: "select", options: [
    { value: "", label: "All States" }, { value: "TX", label: "Texas" },
    { value: "CA", label: "California" }, { value: "FL", label: "Florida" },
    { value: "NY", label: "New York" },
  ]},
  { id: "pharmacy_type", label: "Pharmacy Type", type: "select", options: [
    { value: "", label: "All Types" }, { value: "chain", label: "Retail – Chain" },
    { value: "independent", label: "Independent" }, { value: "mail", label: "Mail Order" },
    { value: "specialty", label: "Specialty" },
  ]},
  { id: "plan", label: "Plan / BIN", type: "text" },
];

const PHARMACY_COLUMNS: Column<PharmaciesData["top_20"][number]>[] = [
  { id: "pharmacy_name", header: "Pharmacy Name", accessor: (r) => r.pharmacy_name, defaultVisible: true, sortable: true, pinned: true },
  { id: "npi", header: "NPI", accessor: (r) => r.npi, defaultVisible: true },
  { id: "ncpdp", header: "NCPDP", accessor: (r) => r.ncpdp, defaultVisible: false },
  { id: "state", header: "State", accessor: (r) => r.state, defaultVisible: true },
  { id: "pharmacy_type", header: "Type", accessor: (r) => r.pharmacy_type, defaultVisible: true },
  { id: "net_claims", header: "Net Claims", accessor: (r) => r.net_claims, format: "number", defaultVisible: true, sortable: true, align: "right" },
  { id: "pct_covered", header: "% Covered", accessor: (r) => r.pct_covered, defaultVisible: true, align: "right",
    cell: (v) => `${(Number(v) * 100).toFixed(0)}%` },
  { id: "total_spend", header: "Total Spend", accessor: (r) => r.total_spend, format: "currency", defaultVisible: true, sortable: true, align: "right" },
  { id: "avg_benefit", header: "Avg Benefit", accessor: (r) => r.avg_benefit, format: "currency", defaultVisible: true, align: "right" },
  { id: "abandonment_rate", header: "Abandonment", accessor: (r) => r.abandonment_rate, defaultVisible: true, align: "right",
    cell: (v) => `${(Number(v) * 100).toFixed(1)}%` },
  { id: "risk_score", header: "Risk Score", accessor: (r) => r.risk_score, defaultVisible: true, sortable: true, align: "right",
    cell: (v) => {
      const n = Number(v);
      const color = n >= 60 ? "text-red-600 font-bold" : n >= 30 ? "text-yellow-600" : "text-green-600";
      return <span className={color}>{n}</span>;
    }},
];

export default function PharmacyInsightsPage() {
  const [filters, setFilters] = useState<FilterValues>({});
  const [selectedState, setSelectedState] = useState<string | null>(null);
  const router = useRouter();

  const { data, isLoading } = useQuery<PharmaciesData>({
    queryKey: ["analytics-pharmacies-summary", filters],
    queryFn: () => apiGet<PharmaciesData>(buildUrl(`${API_URLS.dataiq}/api/v1/analytics/pharmacies/summary`)),
    staleTime: 120_000,
  });

  const kpiCards = data ? [
    { label: "Total Pharmacies", value: data.kpis.total_pharmacies, format: "number" as const },
    { label: "Avg Claims / Pharmacy", value: data.kpis.avg_claims_per_pharmacy, format: "number" as const },
    { label: "Avg Benefit / Pharmacy", value: data.kpis.avg_benefit_per_pharmacy, format: "currency" as const },
    { label: "Total Spend", value: data.kpis.total_spend, format: "currency" as const, accentColor: "#10B981" },
  ] : [];

  const filteredTop20 = data ? (
    selectedState ? data.top_20.filter((p) => p.state === selectedState) : data.top_20
  ) : [];

  return (
    <div className="flex gap-4">
      <FilterPanel filters={FILTERS} values={filters} onChange={setFilters} onClear={() => setFilters({})} />

      <div className="flex-1 min-w-0 space-y-6">
        <div>
          <span className="text-[11px] font-semibold uppercase tracking-wider text-ifx-navy">Analytics</span>
          <h1 className="mt-1 text-2xl font-bold text-ifx-gray-900">Pharmacy Insights</h1>
          <p className="mt-1 text-sm text-ifx-gray-400">Claims by state, top 20 pharmacies, type distribution, and key field pivot table.</p>
        </div>

        {isLoading ? (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24" />)}
          </div>
        ) : (
          <KpiCardRow cards={kpiCards} columns={4} />
        )}

        {/* State Heat Map */}
        <ErrorBoundary>
          <div className="rounded-lg bg-white ifx-card-shadow p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-ifx-gray-900">Claims by State</h3>
              {selectedState && (
                <button
                  type="button"
                  onClick={() => setSelectedState(null)}
                  className="text-xs text-ifx-blue hover:underline"
                >
                  Clear filter: {selectedState}
                </button>
              )}
            </div>
            {isLoading ? <Skeleton className="h-72" /> : data ? (
              <AnalyticsStateChoropleth
                data={data.by_state}
                onStateClick={(abbr) => setSelectedState(abbr === selectedState ? null : abbr)}
              />
            ) : null}
          </div>
        </ErrorBoundary>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Top 20 pharmacies bar */}
          <ErrorBoundary>
            <div className="rounded-lg bg-white ifx-card-shadow p-5">
              <h3 className="text-sm font-semibold text-ifx-gray-900 mb-4">
                Top 20 Pharmacies by Claim Volume
                {selectedState && ` — ${selectedState}`}
              </h3>
              {isLoading ? <Skeleton className="h-96" /> : data ? (
                <AnalyticsTopPharmaciesBar
                  data={filteredTop20}
                  onBarClick={(p) => {
                    const npi = (p as unknown as { npi: string }).npi;
                    if (npi) router.push(`/directories/pharmacies/${npi}`);
                  }}
                />
              ) : null}
            </div>
          </ErrorBoundary>

          {/* Pharmacy type distribution */}
          <ErrorBoundary>
            <div className="rounded-lg bg-white ifx-card-shadow p-5">
              <h3 className="text-sm font-semibold text-ifx-gray-900 mb-4">Pharmacy Type Distribution</h3>
              {isLoading ? <Skeleton className="h-60" /> : data ? (
                <AnalyticsPharmacyTypePie data={data.type_distribution.map((d) => ({ type: d.type, fills: d.count, pct: d.claim_share }))} />
              ) : null}
              {data && (
                <div className="mt-3 space-y-1">
                  {data.type_distribution.map((d) => (
                    <div key={d.type} className="flex items-center justify-between text-xs">
                      <span className="text-ifx-gray-700">{d.type}</span>
                      <span className="text-ifx-gray-400">{d.count} pharmacies · {d.claim_share}% of claims</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </ErrorBoundary>
        </div>

        {/* Pharmacy pivot table */}
        <div className="rounded-lg bg-white ifx-card-shadow p-5">
          <h3 className="text-sm font-semibold text-ifx-gray-900 mb-4">
            Pharmacy Detail Table
            {selectedState && ` — ${selectedState}`}
          </h3>
          {isLoading ? <Skeleton className="h-64" /> : data ? (
            <ConfigurableDataTable
              tableId="analytics-pharmacies-detail"
              columns={PHARMACY_COLUMNS}
              data={filteredTop20}
              searchable
              exportable
              onRowClick={(row) => router.push(`/directories/pharmacies/${row.npi}`)}
            />
          ) : null}
        </div>
      </div>
    </div>
  );
}
