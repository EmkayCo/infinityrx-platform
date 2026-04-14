// Step 3 — Generate Files Preview
"use client";

import React, { useEffect, useState } from "react";
import { FileText, CheckCircle2, Loader2 } from "lucide-react";
import { createBatch, getNachaFile } from "@shared/lib/payments-api";
import { DollarDisplay } from "@shared/components/dollar-display";
import { Skeleton } from "@shared/components/skeleton";
import { PaymentBatchWizardData } from "./types";
import type { NachaPreviewEntry } from "@shared/types/payments";

interface GenerateFilesStepProps {
  data: PaymentBatchWizardData;
  onChange: (partial: Partial<PaymentBatchWizardData>) => void;
}

export function GenerateFilesStep({ data, onChange }: GenerateFilesStepProps) {
  const [loading, setLoading] = useState(!data.batch_id);
  const [error, setError] = useState<string | null>(null);
  const [nachaPreview, setNachaPreview] = useState<NachaPreviewEntry[]>([]);

  useEffect(() => {
    if (data.batch_id) {
      // Already created — load preview
      loadNachaPreview(data.batch_id);
      return;
    }
    if (data.selected_claim_ids.length === 0) {
      setLoading(false);
      return;
    }
    createBatch({ claim_ids: data.selected_claim_ids })
      .then((batch) => {
        onChange({ batch_id: batch.id });
        if (batch.nacha_file_id) {
          return loadNachaPreview(batch.id);
        }
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to generate batch");
      })
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadNachaPreview = async (batchId: string) => {
    try {
      const batch = await import("@shared/lib/payments-api").then((m) =>
        m.getBatch(batchId)
      );
      if (batch.nacha_file_id) {
        const nacha = await getNachaFile(batch.nacha_file_id);
        setNachaPreview(nacha.humanized_preview ?? []);
      }
    } catch {
      // Preview optional — don't block
    }
  };

  if (loading) {
    return (
      <div className="space-y-3">
        <div className="flex items-center gap-2 text-sm text-slate-400">
          <Loader2 className="w-4 h-4 animate-spin text-teal-400" />
          Generating payment files…
        </div>
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded border border-red-500/30 bg-red-500/5 p-3">
        <p className="text-sm text-red-400">{error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-2 text-sm text-teal-400">
        <CheckCircle2 className="w-4 h-4" />
        Payment files generated successfully
      </div>

      {/* File summary cards */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {data.routing_summary.map((r) => (
          <div
            key={r.client_id}
            className="rounded-lg border border-ifx-border-dark bg-navy-700/20 p-4"
          >
            <div className="flex items-start gap-2 mb-3">
              <FileText className="w-4 h-4 text-teal-400 mt-0.5 shrink-0" />
              <div>
                <p className="text-sm font-medium text-slate-200">
                  {r.client_name}
                </p>
                <p className="text-xs text-slate-500">{r.vendor_name}</p>
              </div>
            </div>
            <DollarDisplay amount={r.total_amount} size="md" showScale />
            <p className="text-xs text-slate-500 mt-1">
              {r.payment_count} payment{r.payment_count !== 1 ? "s" : ""}
            </p>
          </div>
        ))}
      </div>

      {/* NACHA humanized preview */}
      {nachaPreview.length > 0 && (
        <div>
          <h4 className="text-sm font-semibold text-slate-300 mb-2">
            NACHA File Preview (humanized)
          </h4>
          <div className="rounded-lg border border-ifx-border-dark bg-navy-900/40 overflow-hidden">
            <div className="overflow-x-auto max-h-72">
              <table className="w-full text-xs font-mono">
                <thead className="bg-navy-900/80 border-b border-ifx-border-dark sticky top-0">
                  <tr>
                    <th className="px-3 py-2 text-left text-slate-400 font-semibold">Type</th>
                    <th className="px-3 py-2 text-left text-slate-400 font-semibold">Description</th>
                    <th className="px-3 py-2 text-right text-slate-400 font-semibold">Amount</th>
                    <th className="px-3 py-2 text-left text-slate-400 font-semibold">Individual</th>
                    <th className="px-3 py-2 text-left text-slate-400 font-semibold">Trace #</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ifx-border-dark/30">
                  {nachaPreview.map((entry, i) => (
                    <tr key={i} className="hover:bg-navy-700/20">
                      <td className="px-3 py-1.5 text-slate-500 capitalize">
                        {entry.line_type.replace(/_/g, " ")}
                      </td>
                      <td className="px-3 py-1.5 text-slate-300">{entry.description}</td>
                      <td className="px-3 py-1.5 text-right">
                        {entry.amount && (
                          <DollarDisplay amount={entry.amount} size="sm" />
                        )}
                      </td>
                      <td className="px-3 py-1.5 text-slate-400">
                        {entry.individual_name ?? "—"}
                      </td>
                      <td className="px-3 py-1.5 text-slate-500">
                        {entry.trace_number ?? "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Showing humanized view. Raw X9.35 file available for download after approval.
          </p>
        </div>
      )}
    </div>
  );
}
