"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle, XCircle, Clock } from "lucide-react";
import { apiGet, apiPost } from "@shared/lib/api-client";
import { ConfigurableDataTable, type Column } from "@/components/ui/configurable-data-table";
import { StatusBadge } from "@/components/ui/status-badge";
import { KpiCardRow } from "@/components/ui/kpi-card-row";

interface PaOverride {
  id: string;
  claim_id: string;
  member_id: string;
  drug_name: string;
  drug_ndc: string;
  prescriber_npi: string;
  prescriber_name?: string;
  diagnosis_code?: string;
  requested_by?: string;
  requested_at: string;
  status: "pending" | "approved" | "denied" | "expired";
  denial_reason?: string;
  approved_at?: string;
  approved_by?: string;
  notes?: string;
  days_supply?: number;
  quantity?: number;
  program_name?: string;
}

interface PaOverrideSummary {
  pending: number;
  approved_today: number;
  denied_today: number;
  avg_turnaround_hours?: number;
}

export default function PaOverridePage() {
  const queryClient = useQueryClient();
  const [actionTarget, setActionTarget] = useState<PaOverride | null>(null);
  const [actionType, setActionType] = useState<"approve" | "deny" | null>(null);
  const [notes, setNotes] = useState("");

  const { data, isLoading } = useQuery<{ items: PaOverride[]; total: number }>({
    queryKey: ["pa-overrides"],
    queryFn: () => apiGet<{ items: PaOverride[]; total: number }>("/api/v1/claims/pa-overrides"),
  });

  const { data: summary } = useQuery<PaOverrideSummary>({
    queryKey: ["pa-override-summary"],
    queryFn: () => apiGet<PaOverrideSummary>("/api/v1/claims/pa-overrides/summary"),
  });

  const actionMutation = useMutation({
    mutationFn: ({ id, action, n }: { id: string; action: "approve" | "deny"; n: string }) =>
      apiPost(`/api/v1/claims/pa-overrides/${id}/${action}`, { notes: n }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["pa-overrides"] });
      void queryClient.invalidateQueries({ queryKey: ["pa-override-summary"] });
      setActionTarget(null);
      setActionType(null);
      setNotes("");
    },
  });

  const rows = data?.items ?? [];
  const pending = rows.filter((r) => r.status === "pending");

  function openAction(row: PaOverride, type: "approve" | "deny") {
    setActionTarget(row);
    setActionType(type);
    setNotes("");
  }

  function confirmAction() {
    if (!actionTarget || !actionType) return;
    actionMutation.mutate({ id: actionTarget.id, action: actionType, n: notes });
  }

  const COLUMNS: Column<PaOverride>[] = [
    {
      id: "requested_at",
      header: "Requested",
      accessor: (r) => r.requested_at,
      format: "date",
      pinned: true,
      defaultVisible: true,
    },
    {
      id: "status",
      header: "Status",
      accessor: (r) => r.status,
      format: "status",
      defaultVisible: true,
    },
    {
      id: "member_id",
      header: "Member ID",
      accessor: (r) => r.member_id,
      defaultVisible: true,
    },
    {
      id: "drug_name",
      header: "Drug",
      accessor: (r) => r.drug_name,
      defaultVisible: true,
    },
    {
      id: "drug_ndc",
      header: "NDC",
      accessor: (r) => r.drug_ndc,
      format: "ndc",
      defaultVisible: true,
    },
    {
      id: "prescriber_name",
      header: "Prescriber",
      accessor: (r) => r.prescriber_name ?? r.prescriber_npi,
      defaultVisible: true,
    },
    {
      id: "diagnosis_code",
      header: "Dx Code",
      accessor: (r) => r.diagnosis_code,
      defaultVisible: true,
    },
    {
      id: "days_supply",
      header: "Days",
      accessor: (r) => r.days_supply,
      format: "number",
      align: "right",
      defaultVisible: true,
    },
    {
      id: "program_name",
      header: "Program",
      accessor: (r) => r.program_name,
      defaultVisible: false,
    },
    {
      id: "requested_by",
      header: "Requested By",
      accessor: (r) => r.requested_by,
      defaultVisible: false,
    },
    {
      id: "approved_by",
      header: "Approved By",
      accessor: (r) => r.approved_by,
      defaultVisible: false,
    },
    {
      id: "denial_reason",
      header: "Denial Reason",
      accessor: (r) => r.denial_reason,
      defaultVisible: false,
    },
    {
      id: "actions",
      header: "Actions",
      accessor: (r) => r.status,
      defaultVisible: true,
      cell: (_value, row) =>
        row.status === "pending" ? (
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); openAction(row, "approve"); }}
              className="inline-flex items-center gap-1 rounded px-2 py-1 text-xs font-medium text-ifx-success hover:bg-ifx-success-light transition-colors"
            >
              <CheckCircle className="h-3.5 w-3.5" />
              Approve
            </button>
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); openAction(row, "deny"); }}
              className="inline-flex items-center gap-1 rounded px-2 py-1 text-xs font-medium text-ifx-error hover:bg-ifx-error-light transition-colors"
            >
              <XCircle className="h-3.5 w-3.5" />
              Deny
            </button>
          </div>
        ) : (
          <StatusBadge status={row.status} />
        ),
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <span className="text-[11px] font-semibold uppercase tracking-wider text-ifx-navy">
            Claims
          </span>
          <h1 className="mt-1 text-2xl font-bold text-ifx-gray-900">PA Override</h1>
          <p className="mt-1 text-sm text-ifx-gray-400">
            Review and action prior authorization override requests.
          </p>
        </div>
        {pending.length > 0 && (
          <div className="flex items-center gap-2 rounded-md bg-ifx-warning-light px-3 py-2 text-sm font-medium text-ifx-warning-text">
            <Clock className="h-4 w-4" />
            {pending.length} request{pending.length !== 1 ? "s" : ""} pending review
          </div>
        )}
      </header>

      <KpiCardRow
        cards={[
          {
            label: "Pending",
            value: summary?.pending ?? pending.length,
            format: "number",
            accentColor: "var(--ifx-warning)",
          },
          {
            label: "Approved Today",
            value: summary?.approved_today ?? 0,
            format: "number",
            accentColor: "var(--ifx-success)",
          },
          {
            label: "Denied Today",
            value: summary?.denied_today ?? 0,
            format: "number",
            accentColor: "var(--ifx-error)",
          },
          {
            label: "Avg Turnaround",
            value: summary?.avg_turnaround_hours
              ? `${summary.avg_turnaround_hours}h`
              : "—",
            format: "raw",
            accentColor: "var(--ifx-blue)",
          },
        ]}
      />

      <ConfigurableDataTable
        tableId="pa-overrides"
        columns={COLUMNS}
        data={rows}
        getRowId={(r) => r.id}
        loading={isLoading}
        emptyMessage="No PA override requests found."
        pagination={{ pageSize: 25 }}
        bulkActions={[
          { id: "approve-selected", label: "Approve Selected", variant: "default" },
          { id: "deny-selected", label: "Deny Selected", variant: "destructive" },
        ]}
        onBulkAction={(action, selectedItems) => {
          const type = action === "approve-selected" ? "approve" : "deny";
          const target = selectedItems.find((r) => r.status === "pending");
          if (target) openAction(target, type);
        }}
      />

      {/* Action modal */}
      {actionTarget && actionType && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-lg bg-white p-6 shadow-xl">
            <h3 className="mb-1 text-base font-bold text-ifx-gray-900">
              {actionType === "approve" ? "Approve" : "Deny"} PA Override
            </h3>
            <p className="mb-4 text-sm text-ifx-gray-400">
              {actionType === "approve" ? "Approving" : "Denying"} override for{" "}
              <strong>{actionTarget.drug_name}</strong> — Member{" "}
              <strong>{actionTarget.member_id}</strong>
            </p>
            <div className="mb-4">
              <label className="mb-1 block text-xs font-medium text-ifx-gray-700">
                Notes{actionType === "deny" ? " (required)" : " (optional)"}
              </label>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={3}
                placeholder={actionType === "deny" ? "Provide denial reason…" : "Optional notes…"}
                className="w-full rounded-md border border-ifx-gray-100 px-3 py-2 text-sm text-ifx-gray-700 placeholder:text-ifx-gray-400 focus:border-ifx-blue focus:outline-none focus:ring-2 focus:ring-ifx-blue/20"
              />
            </div>
            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => { setActionTarget(null); setActionType(null); }}
                className="rounded-md border border-ifx-gray-100 bg-white px-4 py-2 text-sm font-medium text-ifx-gray-700 hover:bg-ifx-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={actionType === "deny" && !notes.trim()}
                onClick={confirmAction}
                className={[
                  "rounded-md px-4 py-2 text-sm font-medium text-white transition-colors disabled:opacity-40",
                  actionType === "approve"
                    ? "bg-ifx-success hover:bg-ifx-success/90"
                    : "bg-ifx-error hover:bg-ifx-error/90",
                ].join(" ")}
              >
                {actionMutation.isPending
                  ? "Processing…"
                  : actionType === "approve"
                    ? "Approve Override"
                    : "Deny Override"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
