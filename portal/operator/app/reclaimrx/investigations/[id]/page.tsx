"use client";

import React, { useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { Check, Upload, ChevronLeft, FileText } from "lucide-react";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { Skeleton } from "@shared/components/skeleton";
import { DollarDisplay } from "@shared/components/dollar-display";
import { ActivityFeed } from "@shared/components/activity-feed";
import { DataTable, type ColDef } from "@shared/components/data-table";
import { apiGet, apiPatch, apiPost, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import type { Investigation, EvidenceItem } from "@shared/types/reclaimrx";
import type { ActivityEvent } from "@shared/types/common";
import { cn, formatDate } from "@shared/lib/format";

const SEVERITY_LABEL: Record<string, string> = {
  critical: "bg-red-900/40 text-red-300",
  high: "bg-orange-900/40 text-orange-300",
  medium: "bg-yellow-900/40 text-yellow-300",
  low: "bg-slate-700 text-slate-400",
};

interface RelatedClaim {
  id: string;
  pharmacy_name: string;
  date_of_service: string;
  drug_name: string;
  billed_amount: string;
  paid_amount: string;
  status: string;
}

const claimColumns: ColDef<RelatedClaim>[] = [
  { accessorKey: "date_of_service", header: "DOS", cell: (c) => formatDate(c.getValue() as string) },
  { accessorKey: "pharmacy_name", header: "Pharmacy" },
  { accessorKey: "drug_name", header: "Drug" },
  { accessorKey: "billed_amount", header: "Billed", cell: (c) => <DollarDisplay amount={c.getValue() as string} size="sm" /> },
  { accessorKey: "paid_amount", header: "Paid", cell: (c) => <DollarDisplay amount={c.getValue() as string} size="sm" /> },
  {
    accessorKey: "status",
    header: "Status",
    cell: (c) => (
      <span className="text-xs px-2 py-0.5 rounded bg-navy-700 text-slate-300 capitalize">
        {c.getValue() as string}
      </span>
    ),
  },
];

function InvestigationDetailInner() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();

  const { data: investigation, isLoading } = useQuery<Investigation>({
    queryKey: ["investigation", id],
    queryFn: () =>
      apiGet<Investigation>(`${API_URLS.reclaimrx}/api/v1/investigations/${id}`),
    staleTime: 30_000,
  });

  // PHI access audit beacon
  useEffect(() => {
    if (investigation) {
      void apiPost(
        `${API_URLS.reclaimrx}/api/v1/investigations/${id}/audit-access`,
        {}
      ).catch(() => {
        // Audit-access beacon is fire-and-forget; never crash the page on failure.
      });
    }
  }, [id, investigation]);

  const toggleEvidence = useMutation({
    mutationFn: (evidenceId: string) =>
      apiPatch(
        `${API_URLS.reclaimrx}/api/v1/investigations/${id}/evidence/${evidenceId}/toggle`,
        {}
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["investigation", id] });
    },
  });

  const { data: claims = [], isLoading: claimsLoading } = useQuery<RelatedClaim[]>({
    queryKey: ["investigation-claims", id],
    queryFn: () =>
      apiGet<RelatedClaim[]>(
        buildUrl(`${API_URLS.reclaimrx}/api/v1/investigations/${id}/claims`)
      ),
    staleTime: 60_000,
    enabled: !!investigation,
  });

  const { data: activityEvents = [] } = useQuery<ActivityEvent[]>({
    queryKey: ["investigation-activity", id],
    queryFn: () =>
      apiGet<ActivityEvent[]>(
        `${API_URLS.reclaimrx}/api/v1/investigations/${id}/activity`
      ),
    staleTime: 30_000,
    enabled: !!investigation,
  });

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40 rounded-lg" />
        <Skeleton className="h-60 rounded-lg" />
      </div>
    );
  }

  // Mock handler returns { error, message } for unknown IDs.
  const notFound =
    !investigation ||
    (investigation as unknown as { error?: string }).error === "not_found";

  if (notFound) {
    return (
      <div className="p-6 space-y-4">
        <h1 className="text-xl font-semibold text-white">Investigation not found</h1>
        <p className="text-sm text-slate-400">
          No investigation exists for ID <span className="font-mono">{id}</span>.
        </p>
        <button
          onClick={() => router.push("/reclaimrx/investigations")}
          className="text-sm text-teal-400 hover:text-teal-300 underline"
        >
          ← Back to investigation queue
        </button>
      </div>
    );
  }

  const { flag } = investigation;
  const completedEvidence = investigation.evidence_items.filter((e) => e.completed).length;
  const totalEvidence = investigation.evidence_items.length;

  return (
    <div className="p-6 space-y-6">
      {/* Back + header */}
      <div className="flex items-start gap-4">
        <button
          onClick={() => router.back()}
          className="flex items-center gap-1 text-sm text-slate-400 hover:text-slate-200 transition-colors mt-1"
        >
          <ChevronLeft className="w-4 h-4" />
          Back
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-2xl font-bold text-white">{flag.entity_name}</h1>
            <span
              className={cn(
                "text-xs px-2 py-1 rounded capitalize",
                SEVERITY_LABEL[flag.severity]
              )}
            >
              {flag.severity}
            </span>
            <span className="text-xs px-2 py-1 rounded bg-navy-700 text-slate-400 capitalize">
              {investigation.status}
            </span>
          </div>
          <p className="text-slate-400 text-sm mt-1 capitalize">
            {flag.flag_type.replace(/_/g, " ")} · {investigation.days_open} days open
            {investigation.assigned_to_name && ` · Assigned to ${investigation.assigned_to_name}`}
          </p>
        </div>
        <button
          onClick={() => router.push(`/reclaimrx/investigations/${id}/wizard`)}
          className="px-4 py-2 rounded-lg bg-teal-600 hover:bg-teal-500 text-white text-sm font-medium transition-colors"
        >
          Continue Investigation →
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Recovery amounts */}
          <div className="grid grid-cols-3 gap-4">
            {[
              { label: "Estimated Recovery", amount: investigation.estimated_recovery },
              { label: "Demanded", amount: investigation.demanded_amount },
              { label: "Collected", amount: investigation.collected_amount },
            ].map(({ label, amount }) => (
              <div
                key={label}
                className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-4"
              >
                <p className="text-xs text-slate-400 mb-1">{label}</p>
                <DollarDisplay amount={amount ?? "0"} size="lg" />
              </div>
            ))}
          </div>

          {/* Flag Evidence */}
          <ErrorBoundary>
            <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
              <h3 className="text-sm font-semibold text-slate-200 mb-3">
                Flag Evidence
              </h3>
              <div className="prose-sm text-slate-300 leading-relaxed whitespace-pre-wrap text-sm">
                {flag.anomaly_narrative || "No narrative available."}
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-400">
                <span>Claims analyzed: {flag.claim_count}</span>
                <span>Detected: {formatDate(flag.detected_at)}</span>
              </div>
            </div>
          </ErrorBoundary>

          {/* Evidence Checklist */}
          <ErrorBoundary>
            <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-slate-200">
                  Evidence Checklist
                </h3>
                <span className="text-xs text-slate-400">
                  {completedEvidence} / {totalEvidence} completed
                </span>
              </div>
              {investigation.evidence_items.length === 0 ? (
                <p className="text-sm text-slate-500">No evidence items defined.</p>
              ) : (
                <div className="space-y-2">
                  {investigation.evidence_items.map((item: EvidenceItem) => (
                    <label
                      key={item.id}
                      className="flex items-start gap-3 p-3 rounded-lg hover:bg-navy-700/30 cursor-pointer"
                    >
                      <button
                        onClick={() => toggleEvidence.mutate(item.id)}
                        className={cn(
                          "flex-shrink-0 w-5 h-5 rounded border-2 flex items-center justify-center transition-colors",
                          item.completed
                            ? "bg-teal-500 border-teal-500"
                            : "border-slate-500 hover:border-teal-500"
                        )}
                        aria-label={`Toggle ${item.label}`}
                      >
                        {item.completed && <Check className="w-3 h-3 text-white" />}
                      </button>
                      <div>
                        <p
                          className={cn(
                            "text-sm",
                            item.completed ? "line-through text-slate-500" : "text-slate-200"
                          )}
                        >
                          {item.label}
                          {item.required && (
                            <span className="text-red-400 ml-1">*</span>
                          )}
                        </p>
                        {item.description && (
                          <p className="text-xs text-slate-500 mt-0.5">
                            {item.description}
                          </p>
                        )}
                      </div>
                    </label>
                  ))}
                </div>
              )}
            </div>
          </ErrorBoundary>

          {/* Related Claims */}
          <ErrorBoundary>
            <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
              <h3 className="text-sm font-semibold text-slate-200 mb-4">
                Related Claims
              </h3>
              <DataTable
                columns={claimColumns}
                data={claims}
                isLoading={claimsLoading}
                emptyTitle="No related claims"
              />
            </div>
          </ErrorBoundary>

          {/* Documents */}
          <ErrorBoundary>
            <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-slate-200">Documents</h3>
                <button className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-navy-700 hover:bg-navy-500 text-slate-300 transition-colors">
                  <Upload className="w-3.5 h-3.5" />
                  Upload
                </button>
              </div>
              <div className="border-2 border-dashed border-ifx-border-dark rounded-lg p-8 text-center">
                <FileText className="w-8 h-8 text-slate-600 mx-auto mb-2" />
                <p className="text-sm text-slate-500">
                  Drop files here or click Upload
                </p>
              </div>
            </div>
          </ErrorBoundary>
        </div>

        {/* Sidebar — Timeline */}
        <div className="space-y-6">
          <ErrorBoundary>
            <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
              <h3 className="text-sm font-semibold text-slate-200 mb-4">
                Action Timeline
              </h3>
              <ActivityFeed events={activityEvents} />
            </div>
          </ErrorBoundary>
        </div>
      </div>
    </div>
  );
}

export default function InvestigationDetailPage() {
  return (
    <ErrorBoundary>
      <InvestigationDetailInner />
    </ErrorBoundary>
  );
}
