// Billing Cycle Detail page.
"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import { useRouter, useParams } from "next/navigation";
import { ArrowLeft, Download, Send, Clock, CheckCircle2 } from "lucide-react";
import { getCycle, transmitNacha } from "@shared/lib/billing-api";
import { DollarDisplay } from "@shared/components/dollar-display";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { SkeletonCard } from "@shared/components/skeleton";
import { formatDate, formatDateTime } from "@shared/lib/format";
import type { BillingCycle, CycleArtifact } from "@shared/types/billing";

function CycleTimeline({ cycle }: { cycle: BillingCycle }) {
  const events = [
    { label: "Created", date: cycle.created_at, done: true },
    { label: "Approved", date: cycle.approved_at, done: !!cycle.approved_at },
    { label: "Generated", date: cycle.generated_at, done: !!cycle.generated_at },
  ];

  return (
    <div className="flex items-center gap-0">
      {events.map((event, i) => (
        <React.Fragment key={event.label}>
          <div className="flex flex-col items-center gap-1 min-w-[100px]">
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center border-2 ${
                event.done
                  ? "border-teal-500 bg-teal-500/20"
                  : "border-slate-700 bg-navy-700"
              }`}
            >
              {event.done ? (
                <CheckCircle2 className="w-4 h-4 text-teal-400" />
              ) : (
                <Clock className="w-4 h-4 text-slate-600" />
              )}
            </div>
            <span className="text-xs font-medium text-slate-300">{event.label}</span>
            {event.date && (
              <span className="text-xs text-slate-500">{formatDate(event.date)}</span>
            )}
          </div>
          {i < events.length - 1 && (
            <div
              className={`flex-1 h-0.5 mt-[-16px] ${
                events[i + 1].done ? "bg-teal-500/60" : "bg-slate-700"
              }`}
            />
          )}
        </React.Fragment>
      ))}
    </div>
  );
}

function ArtifactCard({ artifact, cycleId }: { artifact: CycleArtifact; cycleId: string }) {
  const [transmitting, setTransmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const handleTransmit = async () => {
    setTransmitting(true);
    setError(null);
    try {
      await transmitNacha({ cycle_id: cycleId, artifact_id: artifact.id });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Transmission failed");
    } finally {
      setTransmitting(false);
    }
  };

  const typeLabels: Record<CycleArtifact["type"], string> = {
    saasant_excel: "SaaSant Excel",
    "835": "835 Remittance",
    nacha: "NACHA ACH",
    report: "Report",
  };

  return (
    <div className="flex items-center justify-between p-3 rounded-lg border border-ifx-border-dark bg-navy-700/20">
      <div>
        <p className="text-sm font-medium text-slate-200">
          {typeLabels[artifact.type] ?? artifact.type}
        </p>
        <p className="text-xs text-slate-500 font-mono mt-0.5">{artifact.filename}</p>
        {artifact.transmitted_at && (
          <p className="text-xs text-teal-400 mt-0.5">
            Transmitted {formatDateTime(artifact.transmitted_at)}
            {artifact.ack_status === "acknowledged" && (
              <span className="ml-1 text-green-400">· Acknowledged</span>
            )}
          </p>
        )}
        {error && <p className="text-xs text-red-400 mt-0.5">{error}</p>}
      </div>
      <div className="flex items-center gap-2">
        <a
          href={artifact.download_url}
          download={artifact.filename}
          className="flex items-center gap-1 px-2.5 py-1.5 text-xs rounded border border-ifx-border-dark text-slate-300 hover:bg-navy-700"
        >
          <Download className="w-3.5 h-3.5" />
          Download
        </a>
        {artifact.type === "nacha" && !artifact.transmitted_at && (
          <button
            onClick={handleTransmit}
            disabled={transmitting}
            className="flex items-center gap-1 px-2.5 py-1.5 text-xs rounded bg-teal-500 text-white hover:bg-teal-600 disabled:opacity-40"
          >
            <Send className="w-3.5 h-3.5" />
            {transmitting ? "Transmitting…" : "Transmit"}
          </button>
        )}
      </div>
    </div>
  );
}

export default function CycleDetailPage() {
  const router = useRouter();
  const params = useParams();
  const id = params?.id as string;

  const { data: cycle, isLoading, error } = useQuery({
    queryKey: ["billing-cycle", id],
    queryFn: () => getCycle(id),
    enabled: !!id,
    staleTime: 15_000,
    refetchInterval: 5_000, // Poll while generating
  });

  if (isLoading) {
    return (
      <div className="p-6 space-y-4 max-w-4xl mx-auto">
        <SkeletonCard />
        <SkeletonCard />
      </div>
    );
  }

  if (error || !cycle) {
    return (
      <div className="p-6 max-w-4xl mx-auto">
        <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-6 text-center">
          <p className="text-red-400">
            {error instanceof Error ? error.message : "Billing cycle not found or service unavailable."}
          </p>
          <button
            onClick={() => router.push("/billing")}
            className="mt-3 text-sm text-teal-400 hover:underline"
          >
            Back to Billing
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-start gap-3">
        <button
          onClick={() => router.push("/billing")}
          className="p-1.5 rounded hover:bg-navy-700 text-slate-400 mt-0.5"
          aria-label="Back to billing"
        >
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div>
          <h1 className="text-xl font-bold text-slate-100">
            Billing Cycle — {cycle.cycle_period}
          </h1>
          <p className="text-sm text-slate-400 mt-0.5">
            {cycle.client_name} · {cycle.program_name}
          </p>
        </div>
      </div>

      {/* Timeline */}
      <ErrorBoundary>
        <div className="rounded-lg border border-ifx-border-dark bg-navy-700/20 p-5">
          <h2 className="text-sm font-semibold text-slate-300 mb-4">Timeline</h2>
          <CycleTimeline cycle={cycle} />
        </div>
      </ErrorBoundary>

      {/* Financial summary */}
      <div className="rounded-lg border border-ifx-border-dark bg-navy-700/20 p-5">
        <h2 className="text-sm font-semibold text-slate-300 mb-4">Financial Summary</h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div>
            <p className="text-xs text-slate-500 mb-1">Claims</p>
            <p className="text-lg font-bold tabular-nums text-slate-100">
              {cycle.total_claims.toLocaleString()}
            </p>
          </div>
          <div>
            <p className="text-xs text-slate-500 mb-1">AP Total</p>
            <DollarDisplay amount={cycle.total_ap_amount} size="lg" showScale />
          </div>
          <div>
            <p className="text-xs text-slate-500 mb-1">AR Total</p>
            <DollarDisplay amount={cycle.total_ar_amount} size="lg" showScale />
          </div>
          <div>
            <p className="text-xs text-slate-500 mb-1">Total Fees</p>
            <DollarDisplay amount={cycle.total_fee_amount} size="lg" showScale />
          </div>
        </div>
      </div>

      {/* Artifacts */}
      {cycle.artifacts.length > 0 && (
        <div className="rounded-lg border border-ifx-border-dark bg-navy-700/20 p-5">
          <h2 className="text-sm font-semibold text-slate-300 mb-4">Generated Files</h2>
          <div className="space-y-2">
            {cycle.artifacts.map((a) => (
              <ArtifactCard key={a.id} artifact={a} cycleId={cycle.id} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
