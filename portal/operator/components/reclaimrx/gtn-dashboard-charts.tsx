"use client";

import React from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { Skeleton } from "@shared/components/skeleton";
import type { GTNTrendPoint, LeakageCategory } from "@shared/types/reclaimrx";

const GtnTrendLine = dynamic(
  () =>
    import("@/components/charts/reclaimrx-gtn-trend-line").then(
      (m) => m.ReclaimRxGtnTrendLine
    ),
  { ssr: false, loading: () => <Skeleton className="h-56" /> }
);

const LeakageCategoryDonut = dynamic(
  () =>
    import("@/components/charts/reclaimrx-leakage-category-donut").then(
      (m) => m.ReclaimRxLeakageCategoryDonut
    ),
  { ssr: false, loading: () => <Skeleton className="h-56" /> }
);

const LeakageByProgramBar = dynamic(
  () =>
    import("@/components/charts/reclaimrx-leakage-by-program-bar").then(
      (m) => m.ReclaimRxLeakageByProgramBar
    ),
  { ssr: false, loading: () => <Skeleton className="h-56" /> }
);

interface LeakageByCategoryItem {
  category: LeakageCategory;
  amount: string;
  count: number;
}

interface LeakageByProgramItem {
  program_name: string;
  amount: string;
}

interface TopFlaggedPharmacy {
  npi: string;
  pharmacy_name: string;
  risk_score: number;
  total_leakage: string;
  active_investigations: number;
}

interface Props {
  trendData: GTNTrendPoint[];
  leakageByCategory: LeakageByCategoryItem[];
  leakageByProgram: LeakageByProgramItem[];
  topFlaggedPharmacies: TopFlaggedPharmacy[];
}

function riskColor(score: number): string {
  if (score >= 75) return "text-red-600 bg-red-50";
  if (score >= 50) return "text-orange-600 bg-orange-50";
  if (score >= 25) return "text-yellow-600 bg-yellow-50";
  return "text-green-600 bg-green-50";
}

function fmtMoney(s: string): string {
  const n = parseFloat(s);
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
}

export function GTNDashboardCharts({
  trendData,
  leakageByCategory,
  leakageByProgram,
  topFlaggedPharmacies,
}: Props) {
  const router = useRouter();

  return (
    <div className="space-y-6">
      {/* Row 1: GTN Trend + Leakage by Category */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        <ErrorBoundary>
          <div className="lg:col-span-3 rounded-lg bg-white ifx-card-shadow p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-ifx-gray-700">GTN Ratio Trend</h3>
              <span className="text-xs text-ifx-gray-400">Click a point to see that period&apos;s claims</span>
            </div>
            <GtnTrendLine
              data={trendData}
              onPointClick={(month) =>
                router.push(`/claims?period=${month}`)
              }
            />
          </div>
        </ErrorBoundary>

        <ErrorBoundary>
          <div className="lg:col-span-2 rounded-lg bg-white ifx-card-shadow p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-ifx-gray-700">Leakage by Category</h3>
              <Link href="/reclaimrx/leakage" className="text-xs text-ifx-blue hover:underline">
                View all →
              </Link>
            </div>
            <LeakageCategoryDonut data={leakageByCategory} />
          </div>
        </ErrorBoundary>
      </div>

      {/* Row 2: Leakage by Program + Top Flagged Pharmacies */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ErrorBoundary>
          <div className="rounded-lg bg-white ifx-card-shadow p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-ifx-gray-700">Leakage by Program</h3>
              <span className="text-xs text-ifx-gray-400">Click bar to see program detail</span>
            </div>
            <LeakageByProgramBar data={leakageByProgram} />
          </div>
        </ErrorBoundary>

        <ErrorBoundary>
          <div className="rounded-lg bg-white ifx-card-shadow p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-ifx-gray-700">Top Flagged Pharmacies</h3>
              <Link href="/reclaimrx/risk" className="text-xs text-ifx-blue hover:underline">
                Full risk table →
              </Link>
            </div>
            <div className="space-y-2">
              {topFlaggedPharmacies.map((p) => (
                <div
                  key={p.npi}
                  className="flex items-center justify-between p-3 rounded-lg hover:bg-ifx-gray-50 cursor-pointer transition-colors border border-ifx-gray-100"
                  onClick={() => router.push(`/reclaimrx/risk`)}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <span
                      className={`text-xs font-bold px-2 py-1 rounded ${riskColor(p.risk_score)}`}
                    >
                      {p.risk_score}
                    </span>
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-ifx-gray-700 truncate">
                        {p.pharmacy_name}
                      </p>
                      <p className="text-xs text-ifx-gray-400 font-mono">NPI {p.npi}</p>
                    </div>
                  </div>
                  <div className="text-right flex-shrink-0 ml-3">
                    <p className="text-sm font-semibold text-red-600">
                      {fmtMoney(p.total_leakage)}
                    </p>
                    {p.active_investigations > 0 && (
                      <p className="text-xs text-orange-500">
                        {p.active_investigations} open
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </ErrorBoundary>
      </div>
    </div>
  );
}
