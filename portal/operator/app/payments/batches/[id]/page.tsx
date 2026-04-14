// Payment Batch detail page.
"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import { useRouter, useParams } from "next/navigation";
import { ArrowLeft, CheckCircle2, Clock, XCircle, Loader2 } from "lucide-react";
import { getBatch, getNachaFile } from "@shared/lib/payments-api";
import { DollarDisplay } from "@shared/components/dollar-display";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { SkeletonCard } from "@shared/components/skeleton";
import { formatDateTime } from "@shared/lib/format";
import type { NachaPreviewEntry } from "@shared/types/payments";

function StatusIcon({ status }: { status: string }) {
  if (status === "settled" || status === "acknowledged") return <CheckCircle2 className="w-4 h-4 text-green-400" />;
  if (status === "failed") return <XCircle className="w-4 h-4 text-red-400" />;
  if (status === "transmitting" || status === "generating") return <Loader2 className="w-4 h-4 text-teal-400 animate-spin" />;
  return <Clock className="w-4 h-4 text-slate-500" />;
}

export default function BatchDetailPage() {
  const router = useRouter();
  const params = useParams();
  const id = params?.id as string;

  const { data: batch, isLoading } = useQuery({
    queryKey: ["payment-batch", id],
    queryFn: () => getBatch(id),
    enabled: !!id,
    refetchInterval: 5_000,
  });

  const { data: nachaFile } = useQuery({
    queryKey: ["nacha-file", batch?.nacha_file_id],
    queryFn: () => getNachaFile(batch!.nacha_file_id!),
    enabled: !!batch?.nacha_file_id,
  });

  if (isLoading) {
    return (
      <div className="p-6 space-y-4 max-w-4xl mx-auto">
        <SkeletonCard />
        <SkeletonCard />
      </div>
    );
  }

  if (!batch) {
    return (
      <div className="p-6 max-w-4xl mx-auto">
        <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-6 text-center">
          <p className="text-red-400">Payment batch not found or service unavailable.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-5">
      {/* Header */}
      <div className="flex items-start gap-3">
        <button
          onClick={() => router.push("/payments")}
          className="p-1.5 rounded hover:bg-navy-700 text-slate-400 mt-0.5"
          aria-label="Back"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div>
          <h1 className="text-xl font-bold text-slate-100">Payment Batch</h1>
          <p className="text-sm font-mono text-slate-400 mt-0.5">{batch.id}</p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <StatusIcon status={batch.status} />
          <span className="text-sm text-slate-300 capitalize">
            {batch.status.replace(/_/g, " ")}
          </span>
        </div>
      </div>

      {/* Summary */}
      <div className="rounded-lg border border-ifx-border-dark bg-navy-700/20 p-5 grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div>
          <p className="text-xs text-slate-500 mb-1">Vendor</p>
          <p className="text-sm font-medium text-slate-200">{batch.vendor_name}</p>
        </div>
        <div>
          <p className="text-xs text-slate-500 mb-1">Payments</p>
          <p className="text-lg font-bold tabular-nums text-slate-100">
            {batch.payment_count.toLocaleString()}
          </p>
        </div>
        <div>
          <p className="text-xs text-slate-500 mb-1">Total Amount</p>
          <DollarDisplay amount={batch.total_amount} size="lg" showScale />
        </div>
        <div>
          <p className="text-xs text-slate-500 mb-1">Ack Status</p>
          <p className={`text-sm font-medium ${
            batch.ack_status === "acknowledged" ? "text-green-400" :
            batch.ack_status === "rejected" ? "text-red-400" :
            "text-yellow-400"
          }`}>
            {batch.ack_status ?? "—"}
          </p>
        </div>
      </div>

      {/* Timeline */}
      <div className="rounded-lg border border-ifx-border-dark bg-navy-700/20 p-4 space-y-2">
        <h3 className="text-sm font-semibold text-slate-300">Timeline</h3>
        {[
          { label: "Created", date: batch.created_at },
          { label: "Approved", date: batch.approved_at },
          { label: "Transmitted", date: batch.transmitted_at },
          { label: "Ack received", date: batch.ack_received_at },
        ]
          .filter((e) => e.date)
          .map((event) => (
            <div key={event.label} className="flex gap-4 text-sm">
              <span className="text-slate-500 w-28">{event.label}</span>
              <span className="text-slate-200">{formatDateTime(event.date)}</span>
            </div>
          ))}
      </div>

      {/* NACHA humanized preview */}
      {nachaFile && nachaFile.humanized_preview.length > 0 && (
        <ErrorBoundary>
          <div className="rounded-lg border border-ifx-border-dark bg-navy-900/40">
            <div className="px-4 py-3 border-b border-ifx-border-dark flex items-center justify-between">
              <h3 className="text-sm font-semibold text-slate-300">
                NACHA File Preview (humanized)
              </h3>
              <a
                href={nachaFile.download_url}
                download={nachaFile.filename}
                className="text-xs text-teal-400 hover:underline"
              >
                Download raw file
              </a>
            </div>
            <div className="overflow-x-auto max-h-64">
              <table className="w-full text-xs font-mono">
                <thead className="bg-navy-900/80 border-b border-ifx-border-dark sticky top-0">
                  <tr>
                    <th className="px-3 py-2 text-left text-slate-400 font-semibold">Type</th>
                    <th className="px-3 py-2 text-left text-slate-400 font-semibold">Description</th>
                    <th className="px-3 py-2 text-right text-slate-400 font-semibold">Amount</th>
                    <th className="px-3 py-2 text-left text-slate-400 font-semibold">Individual</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ifx-border-dark/30">
                  {nachaFile.humanized_preview.map((entry: NachaPreviewEntry, i: number) => (
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
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </ErrorBoundary>
      )}
    </div>
  );
}
