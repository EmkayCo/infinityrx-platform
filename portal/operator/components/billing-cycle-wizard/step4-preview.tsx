// Step 4 — Preview
"use client";

import React, { useEffect, useState } from "react";
import { TrendingUp, TrendingDown, AlertTriangle, Info } from "lucide-react";
import { getFinancialPreview } from "@shared/lib/billing-api";
import { DollarDisplay } from "@shared/components/dollar-display";
import { Skeleton } from "@shared/components/skeleton";
import { cn } from "@shared/lib/format";
import { BillingCycleWizardData } from "./types";
import type { FinancialPreview } from "@shared/types/billing";

interface PreviewStepProps {
  data: BillingCycleWizardData;
  onChange: (partial: Partial<BillingCycleWizardData>) => void;
}

export function PreviewStep({ data, onChange }: PreviewStepProps) {
  const [loading, setLoading] = useState(!data.financial_preview);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!data.financial_preview && data.upload_id) {
      setLoading(true);
      getFinancialPreview(data.upload_id)
        .then((fp: FinancialPreview) => {
          onChange({ financial_preview: fp });
        })
        .catch((err: unknown) => {
          setError(err instanceof Error ? err.message : "Failed to load financial preview");
        })
        .finally(() => setLoading(false));
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fp = data.financial_preview;

  return (
    <div className="space-y-6">
      {/* Summary cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <SummaryCard
          label="Total Claims"
          loading={loading}
          value={
            data.total_claims != null
              ? data.total_claims.toLocaleString()
              : "—"
          }
        />
        <SummaryCard
          label="AP Total"
          loading={loading}
          value={
            fp ? (
              <DollarDisplay amount={fp.ap_total} size="lg" showScale />
            ) : (
              <DollarDisplay amount={data.total_ap_amount} size="lg" showScale />
            )
          }
        />
        <SummaryCard
          label="AR Total"
          loading={loading}
          value={
            fp ? (
              <DollarDisplay amount={fp.ar_total} size="lg" showScale />
            ) : (
              <DollarDisplay amount={data.total_ar_amount} size="lg" showScale />
            )
          }
        />
        <SummaryCard
          label="Total Fees"
          loading={loading}
          value={
            fp ? (
              <DollarDisplay amount={fp.fee_total} size="lg" showScale />
            ) : (
              <DollarDisplay amount={data.total_fee_amount} size="lg" showScale />
            )
          }
        />
      </div>

      {/* Error state */}
      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-3 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />
          <span className="text-sm text-red-400">{error}</span>
        </div>
      )}

      {/* Financial preview */}
      {loading && (
        <div className="space-y-3">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      )}

      {fp && !loading && (
        <div className="space-y-4">
          {/* Net settlement */}
          <div className="rounded-lg border border-teal-500/30 bg-teal-500/5 p-4">
            <p className="text-sm text-slate-400 mb-1">Net Settlement</p>
            <DollarDisplay amount={fp.net_settlement} size="xl" showScale showVerbal />
          </div>

          {/* Journal entries preview */}
          {fp.journal_entries.length > 0 && (
            <div>
              <h4 className="text-sm font-semibold text-slate-300 mb-2">
                Journal Entries Preview
              </h4>
              <div className="rounded-lg border border-ifx-border-dark overflow-hidden">
                <table className="w-full text-xs">
                  <thead className="bg-navy-900/80 border-b border-ifx-border-dark">
                    <tr>
                      <th className="px-3 py-2 text-left text-slate-400 font-semibold uppercase tracking-wide">Account</th>
                      <th className="px-3 py-2 text-right text-slate-400 font-semibold uppercase tracking-wide">Debit</th>
                      <th className="px-3 py-2 text-right text-slate-400 font-semibold uppercase tracking-wide">Credit</th>
                      <th className="px-3 py-2 text-left text-slate-400 font-semibold uppercase tracking-wide">Description</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-ifx-border-dark/50">
                    {fp.journal_entries.map((entry, i) => (
                      <tr key={i} className="hover:bg-navy-700/20">
                        <td className="px-3 py-2 font-mono text-slate-200">{entry.account}</td>
                        <td className="px-3 py-2 text-right tabular-nums">
                          {entry.debit !== "0.00" ? (
                            <DollarDisplay amount={entry.debit} size="sm" />
                          ) : (
                            <span className="text-slate-600">—</span>
                          )}
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums">
                          {entry.credit !== "0.00" ? (
                            <DollarDisplay amount={entry.credit} size="sm" />
                          ) : (
                            <span className="text-slate-600">—</span>
                          )}
                        </td>
                        <td className="px-3 py-2 text-slate-400">{entry.description}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Anomaly flags */}
      <AnomalyFlags />

      <div className="flex items-start gap-2 rounded-lg bg-ifx-info/5 border border-ifx-info/20 p-3">
        <Info className="w-4 h-4 text-blue-400 mt-0.5 shrink-0" />
        <p className="text-xs text-slate-400">
          Review all amounts carefully. Once approved in the next step, the system will
          generate 835, NACHA, SaaSant Excel, and all configured report outputs.
        </p>
      </div>
    </div>
  );
}

function SummaryCard({
  label,
  value,
  loading,
}: {
  label: string;
  value: React.ReactNode;
  loading?: boolean;
}) {
  return (
    <div className="rounded-lg border border-ifx-border-dark bg-navy-700/20 p-4">
      <p className="text-xs text-slate-500 uppercase tracking-wide mb-1">{label}</p>
      {loading ? (
        <Skeleton className="h-7 w-24" />
      ) : (
        <div className="text-slate-100">{value}</div>
      )}
    </div>
  );
}

function AnomalyFlags() {
  // Placeholder — in production, these come from the backend AI narrative
  const flags: Array<{ severity: "info" | "warning" | "critical"; message: string }> = [
    {
      severity: "warning",
      message: "This cycle is 12% higher than the 3-month average. Review before approving.",
    },
  ];

  return (
    <div className="space-y-2">
      {flags.map((flag, i) => (
        <div
          key={i}
          className={cn(
            "flex items-start gap-2 rounded-lg border p-3",
            flag.severity === "warning" && "border-yellow-500/30 bg-yellow-500/5",
            flag.severity === "info" && "border-blue-500/30 bg-blue-500/5"
          )}
        >
          {flag.severity === "warning" ? (
            <TrendingUp className="w-4 h-4 text-yellow-400 mt-0.5 shrink-0" />
          ) : (
            <TrendingDown className="w-4 h-4 text-blue-400 mt-0.5 shrink-0" />
          )}
          <p className="text-sm text-slate-300">{flag.message}</p>
        </div>
      ))}
    </div>
  );
}
