// Claims Review page — DataTable with bulk actions and slide-out detail.
"use client";

import React, { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { listClaims, getClaim, bulkUpdateClaimStatus } from "@shared/lib/billing-api";
import { DataTable, type ColDef } from "@shared/components/data-table";
import { DollarCell, DollarDisplay } from "@shared/components/dollar-display";
import { ExportMenu } from "@shared/components/export-menu";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { SkeletonTable } from "@shared/components/skeleton";
import { formatDate } from "@shared/lib/format";
import type { Claim, ClaimStatus } from "@shared/types/billing";

const STATUS_CLASSES: Record<ClaimStatus, string> = {
  pending: "bg-slate-700 text-slate-300",
  valid: "bg-teal-500/20 text-teal-300",
  warning: "bg-yellow-500/20 text-yellow-300",
  error: "bg-red-500/20 text-red-300",
  approved: "bg-green-500/20 text-green-300",
  rejected: "bg-red-700/30 text-red-400",
  flagged: "bg-orange-500/20 text-orange-300",
};

function ClaimDetailSheet({
  claimId,
  onClose,
}: {
  claimId: string;
  onClose: () => void;
}) {
  const { data: claim, isLoading } = useQuery({
    queryKey: ["claim", claimId],
    queryFn: () => getClaim(claimId),
  });

  return (
    <aside
      className="fixed inset-y-0 right-0 w-96 bg-navy-900 border-l border-ifx-border-dark shadow-2xl z-50 overflow-y-auto"
      aria-label="Claim detail"
    >
      <div className="flex items-center justify-between p-4 border-b border-ifx-border-dark">
        <h3 className="font-semibold text-slate-200">Claim Detail</h3>
        <button
          onClick={onClose}
          className="p-1 rounded hover:bg-navy-700 text-slate-400"
          aria-label="Close"
        >
          ×
        </button>
      </div>
      {isLoading ? (
        <div className="p-4 space-y-3">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="h-4 rounded bg-slate-700/50 animate-pulse" />
          ))}
        </div>
      ) : claim ? (
        <div className="p-4 space-y-4">
          <dl className="space-y-3 text-sm">
            {[
              { label: "Claim ID", value: claim.id },
              { label: "Client", value: claim.client_name },
              { label: "Program", value: claim.program_name },
              { label: "Pharmacy", value: claim.pharmacy_name },
              { label: "NPI", value: claim.pharmacy_npi },
              { label: "Member ID", value: claim.member_id },
              { label: "Drug", value: claim.drug_name },
              { label: "NDC", value: claim.drug_ndc },
              { label: "Fill Date", value: formatDate(claim.fill_date) },
              { label: "Days Supply", value: String(claim.days_supply) },
              { label: "Quantity", value: claim.quantity },
            ].map(({ label, value }) => (
              <div key={label} className="flex justify-between gap-3">
                <dt className="text-slate-500">{label}</dt>
                <dd className="text-slate-200 font-mono text-xs text-right truncate">{value}</dd>
              </div>
            ))}
          </dl>
          <div className="rounded-lg border border-ifx-border-dark bg-navy-700/20 p-3 space-y-2">
            <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wide">Financials</h4>
            {[
              { label: "Ingredient Cost", amount: claim.ingredient_cost },
              { label: "Dispensing Fee", amount: claim.dispensing_fee },
              { label: "Copay", amount: claim.copay },
              { label: "Plan Paid", amount: claim.plan_paid },
            ].map(({ label, amount }) => (
              <div key={label} className="flex justify-between items-center text-sm">
                <span className="text-slate-500">{label}</span>
                <DollarDisplay amount={amount} size="sm" />
              </div>
            ))}
          </div>
          {claim.rejection_reason && (
            <div className="rounded border border-red-500/30 bg-red-500/5 p-3">
              <p className="text-xs font-medium text-red-400 mb-1">Rejection Reason</p>
              <p className="text-sm text-slate-300">{claim.rejection_reason}</p>
            </div>
          )}
        </div>
      ) : null}
    </aside>
  );
}

export default function ClaimsPage() {
  const queryClient = useQueryClient();
  const [selectedClaimId, setSelectedClaimId] = useState<string | null>(null);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [statusFilter, setStatusFilter] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["claims", statusFilter],
    queryFn: () => listClaims({ status: statusFilter || undefined, page_size: 200 }),
    staleTime: 30_000,
  });

  const claims = data?.data ?? [];

  const bulkMutation = useMutation({
    mutationFn: ({
      action,
    }: {
      action: "approve" | "reject" | "flag";
    }) => bulkUpdateClaimStatus(selectedIds, action),
    onSuccess: (result, { action }) => {
      queryClient.invalidateQueries({ queryKey: ["claims"] });
      const verb = action === "approve" ? "approved" : action === "reject" ? "rejected" : "flagged";
      toast.success(
        `${result.success_count} claim${result.success_count !== 1 ? "s" : ""} ${verb}`,
        {
          action:
            result.failures.length === 0
              ? {
                  label: "Undo",
                  onClick: () => {
                    // Optimistic undo — re-fetch
                    queryClient.invalidateQueries({ queryKey: ["claims"] });
                  },
                }
              : undefined,
          description:
            result.failures.length > 0
              ? `${result.failures.length} failed — ${result.failures
                  .slice(0, 3)
                  .map((f) => f.reason)
                  .join("; ")}`
              : undefined,
        }
      );
      setSelectedIds([]);
    },
    onError: (err) => {
      toast.error(
        err instanceof Error ? err.message : "Bulk action failed"
      );
    },
  });

  const columns: ColDef<Claim>[] = [
    {
      id: "select",
      header: () => null,
      cell: ({ row }) => (
        <input
          type="checkbox"
          checked={selectedIds.includes(row.original.id)}
          onChange={(e) => {
            setSelectedIds((prev) =>
              e.target.checked
                ? [...prev, row.original.id]
                : prev.filter((id) => id !== row.original.id)
            );
          }}
          onClick={(e) => e.stopPropagation()}
          aria-label={`Select claim ${row.original.id}`}
          className="rounded border-ifx-border-dark bg-navy-900 text-teal-500"
        />
      ),
      size: 48,
      enableSorting: false,
    },
    { accessorKey: "client_name", header: "Client", size: 140 },
    { accessorKey: "pharmacy_name", header: "Pharmacy", size: 160 },
    { accessorKey: "drug_name", header: "Drug", size: 140 },
    {
      accessorKey: "fill_date",
      header: "Fill Date",
      cell: ({ row }) => formatDate(row.original.fill_date),
      size: 110,
    },
    {
      accessorKey: "plan_paid",
      header: "Plan Paid",
      cell: ({ row }) => <DollarCell amount={row.original.plan_paid} />,
      size: 110,
    },
    {
      accessorKey: "status",
      header: "Status",
      cell: ({ row }) => (
        <span
          className={`px-2 py-0.5 rounded text-xs font-medium ${
            STATUS_CLASSES[row.original.status] ?? "bg-slate-700 text-slate-300"
          }`}
        >
          {row.original.status}
        </span>
      ),
      size: 100,
    },
  ];

  const handleExportCsv = () => {
    const rows = claims.map((c) => [
      c.id,
      c.client_name,
      c.pharmacy_name,
      c.drug_ndc,
      c.fill_date,
      c.plan_paid,
      c.status,
    ]);
    const csv =
      "ID,Client,Pharmacy,NDC,Fill Date,Plan Paid,Status\n" +
      rows.map((r) => r.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "claims.csv";
    a.click();
  };

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-slate-100">Claims Review</h1>
        <ExportMenu onExportCsv={handleExportCsv} />
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3 py-1.5 text-sm rounded-md border border-ifx-border-dark bg-navy-900 text-white focus:outline-none focus:ring-2 focus:ring-teal-500/40"
          aria-label="Filter by status"
        >
          <option value="">All statuses</option>
          {["pending", "valid", "warning", "error", "approved", "rejected", "flagged"].map(
            (s) => (
              <option key={s} value={s}>
                {s.charAt(0).toUpperCase() + s.slice(1)}
              </option>
            )
          )}
        </select>
      </div>

      {/* Bulk action bar */}
      {selectedIds.length > 0 && (
        <div className="flex items-center gap-4 px-4 py-2.5 rounded-lg bg-teal-900/30 border border-teal-600/30">
          <span className="text-sm font-medium text-teal-300">
            {selectedIds.length} selected
          </span>
          <div className="flex gap-2">
            {(["approve", "reject", "flag"] as const).map((action) => (
              <button
                key={action}
                onClick={() => bulkMutation.mutate({ action })}
                disabled={bulkMutation.isPending}
                className="px-3 py-1 text-xs rounded border border-ifx-border-dark text-slate-300 hover:bg-navy-700 disabled:opacity-40 capitalize"
              >
                {action}
              </button>
            ))}
          </div>
        </div>
      )}

      <ErrorBoundary>
        {isLoading ? (
          <SkeletonTable rows={8} cols={7} />
        ) : (
          <DataTable
            columns={columns}
            data={claims}
            onRowClick={(row) => setSelectedClaimId(row.id)}
            emptyTitle="No claims found"
            emptyDescription="No claims match the current filters."
            stickyHeader
          />
        )}
      </ErrorBoundary>

      {/* Claim detail slide-out */}
      {selectedClaimId && (
        <ClaimDetailSheet
          claimId={selectedClaimId}
          onClose={() => setSelectedClaimId(null)}
        />
      )}
    </div>
  );
}
