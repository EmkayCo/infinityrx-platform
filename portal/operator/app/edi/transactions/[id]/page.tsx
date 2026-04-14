"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { ChevronLeft, Eye, Code } from "lucide-react";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { Skeleton } from "@shared/components/skeleton";
import { apiGet } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import type { EDITransaction } from "@shared/types/edi";
import { formatDateTime } from "@shared/lib/format";

export default function TransactionDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [showRaw, setShowRaw] = useState(false);

  const { data: tx, isLoading } = useQuery<EDITransaction>({
    queryKey: ["edi-transaction", id],
    queryFn: () => apiGet<EDITransaction>(`${API_URLS.edi}/api/v1/transactions/${id}`),
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

  if (!tx) return <div className="p-6"><p className="text-slate-400">Transaction not found.</p></div>;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-4">
        <button onClick={() => router.back()} className="flex items-center gap-1 text-sm text-slate-400 hover:text-slate-200 transition-colors">
          <ChevronLeft className="w-4 h-4" /> Back
        </button>
        <div className="flex-1">
          <h1 className="text-xl font-bold text-white font-mono">{tx.filename}</h1>
          <p className="text-slate-400 text-sm">{tx.partner_name} · {formatDateTime(tx.received_at)}</p>
        </div>
        <button
          onClick={() => setShowRaw(!showRaw)}
          className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-ifx-border-dark text-slate-300 hover:bg-navy-700 text-sm transition-colors"
        >
          {showRaw ? <Eye className="w-4 h-4" /> : <Code className="w-4 h-4" />}
          {showRaw ? "Parsed View" : "Raw View"}
        </button>
      </div>

      {/* Envelope Details */}
      <ErrorBoundary>
        <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
          <h3 className="text-sm font-semibold text-slate-200 mb-4">Envelope Details</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
            {[
              { label: "Type", value: tx.transaction_type },
              { label: "Direction", value: tx.direction },
              { label: "Status", value: tx.status },
              { label: "Transactions", value: String(tx.transaction_count) },
              { label: "ISA Control", value: tx.interchange_control_number ?? "—" },
              { label: "GS Group", value: tx.functional_group_id ?? "—" },
              { label: "Received", value: formatDateTime(tx.received_at) },
              { label: "Processed", value: tx.processed_at ? formatDateTime(tx.processed_at) : "—" },
            ].map(({ label, value }) => (
              <div key={label}>
                <p className="text-slate-500 mb-0.5">{label}</p>
                <p className="text-white font-mono">{value}</p>
              </div>
            ))}
          </div>
        </div>
      </ErrorBoundary>

      {/* Validation Errors */}
      {tx.validation_errors && tx.validation_errors.length > 0 && (
        <ErrorBoundary>
          <div className="rounded-lg border border-red-700/30 bg-red-900/5 p-5">
            <h3 className="text-sm font-semibold text-red-300 mb-3">
              Validation Errors ({tx.validation_errors.length})
            </h3>
            <div className="space-y-1.5">
              {tx.validation_errors.map((err, i) => (
                <div key={i} className="text-xs flex gap-3">
                  <span className="font-mono text-slate-500 w-12">{err.segment}</span>
                  <span className="font-mono text-slate-400 w-12">{err.element}</span>
                  <span className="text-red-400 font-mono">[{err.error_code}]</span>
                  <span className="text-slate-300">{err.message}</span>
                </div>
              ))}
            </div>
          </div>
        </ErrorBoundary>
      )}

      {/* Raw/Preview */}
      {showRaw && tx.raw_preview && (
        <ErrorBoundary>
          <div className="rounded-lg border border-ifx-border-dark bg-navy-900/60 p-5">
            <h3 className="text-sm font-semibold text-slate-200 mb-3">Raw EDI</h3>
            <pre className="text-xs text-slate-300 font-mono overflow-x-auto whitespace-pre-wrap leading-relaxed">
              {tx.raw_preview}
            </pre>
          </div>
        </ErrorBoundary>
      )}
    </div>
  );
}
