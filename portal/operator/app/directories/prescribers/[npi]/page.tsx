"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { ChevronLeft, AlertTriangle, CheckCircle, XCircle } from "lucide-react";
import dynamic from "next/dynamic";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { Skeleton } from "@shared/components/skeleton";
import { apiGet } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import type { Prescriber } from "@shared/types/directories";
import { formatDate } from "@shared/lib/format";

const DirectoriesPrescriberTopDrugsBar = dynamic(
  () =>
    import("@/components/charts/directories-prescriber-top-drugs-bar").then(
      (m) => m.DirectoriesPrescriberTopDrugsBar
    ),
  { ssr: false, loading: () => <Skeleton className="h-48" /> }
);

export default function PrescriberDetailPage() {
  const { npi } = useParams<{ npi: string }>();
  const router = useRouter();

  const { data: prescriber, isLoading } = useQuery<Prescriber>({
    queryKey: ["prescriber", npi],
    queryFn: () =>
      apiGet<Prescriber>(`${API_URLS.prescriberDirectory}/api/v1/prescribers/${npi}`),
    staleTime: 60_000,
  });

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-48 rounded-lg" />
      </div>
    );
  }

  if (!prescriber) {
    return <div className="p-6"><p className="text-slate-400">Prescriber not found.</p></div>;
  }

  const topDrugs = prescriber.prescribing_summary?.top_drugs ?? [];

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-4">
        <button onClick={() => router.back()} className="flex items-center gap-1 text-sm text-slate-400 hover:text-slate-200 transition-colors">
          <ChevronLeft className="w-4 h-4" /> Back
        </button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-white">{prescriber.full_name}</h1>
          <p className="text-slate-400 text-sm">{prescriber.specialty} · NPI: {prescriber.npi}</p>
        </div>
      </div>

      {prescriber.credential_alerts.length > 0 && (
        <div className="rounded-lg border border-orange-700/30 bg-orange-900/10 p-4">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className="w-4 h-4 text-orange-400" />
            <span className="text-sm font-medium text-orange-300">Credential Alerts</span>
          </div>
          <ul className="space-y-1">
            {prescriber.credential_alerts.map((alert, i) => (
              <li key={i} className="text-xs text-orange-300 flex items-start gap-1.5">
                <span className="mt-0.5">•</span>{alert}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Demographics */}
        <ErrorBoundary>
          <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5 space-y-3">
            <h3 className="text-sm font-semibold text-slate-200">Details</h3>
            <div className="space-y-2 text-xs">
              {prescriber.subspecialty && (
                <p><span className="text-slate-500">Subspecialty:</span> <span className="text-slate-300">{prescriber.subspecialty}</span></p>
              )}
              {prescriber.city && (
                <p><span className="text-slate-500">Location:</span> <span className="text-slate-300">{prescriber.city}, {prescriber.state}</span></p>
              )}
              {prescriber.phone && (
                <p><span className="text-slate-500">Phone:</span> <span className="text-slate-300">{prescriber.phone}</span></p>
              )}
            </div>
          </div>
        </ErrorBoundary>

        {/* DEA / License Status */}
        <ErrorBoundary>
          <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
            <h3 className="text-sm font-semibold text-slate-200 mb-4">Credentials</h3>
            <div className="space-y-3">
              {[
                {
                  label: "DEA Registration",
                  status: prescriber.dea_status === "active",
                  detail: prescriber.dea_number ?? "None",
                  expiry: prescriber.dea_expiry,
                },
                {
                  label: "State License",
                  status: prescriber.state_license_status === "active",
                  detail: prescriber.state_license_number ?? "None",
                  expiry: prescriber.state_license_expiry,
                },
              ].map((cred) => (
                <div key={cred.label} className="flex items-start gap-2.5">
                  {cred.status ? (
                    <CheckCircle className="w-4 h-4 text-green-400 flex-shrink-0 mt-0.5" />
                  ) : (
                    <XCircle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
                  )}
                  <div>
                    <p className="text-sm text-slate-200">{cred.label}</p>
                    <p className="text-xs text-slate-400">{cred.detail}</p>
                    {cred.expiry && (
                      <p className="text-xs text-slate-500">Expires: {formatDate(cred.expiry)}</p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </ErrorBoundary>

        {/* Prescribing Summary */}
        <ErrorBoundary>
          <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
            <h3 className="text-sm font-semibold text-slate-200 mb-2">Prescribing Summary</h3>
            {prescriber.prescribing_summary ? (
              <div className="space-y-1 text-xs text-slate-400">
                <p>Claims (90d): <span className="text-white">{prescriber.prescribing_summary.total_claims_90d}</span></p>
                <p>Avg Days Supply: <span className="text-white">{prescriber.prescribing_summary.avg_days_supply}</span></p>
              </div>
            ) : (
              <p className="text-xs text-slate-500 italic">No prescribing data available.</p>
            )}
          </div>
        </ErrorBoundary>
      </div>

      {/* Top Drugs Chart */}
      {topDrugs.length > 0 && (
        <ErrorBoundary>
          <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
            <h3 className="text-sm font-semibold text-slate-200 mb-4">Top Prescribed Drugs (90 days)</h3>
            <DirectoriesPrescriberTopDrugsBar data={topDrugs} />
          </div>
        </ErrorBoundary>
      )}
    </div>
  );
}
