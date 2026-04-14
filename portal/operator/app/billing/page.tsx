// Billing landing page — active cycles DataTable + navigation.
"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { Plus, RefreshCw } from "lucide-react";
import { listCycles } from "@shared/lib/billing-api";
import { DataTable, type ColDef } from "@shared/components/data-table";
import { DollarCell } from "@shared/components/dollar-display";
import { ExportMenu } from "@shared/components/export-menu";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { SkeletonTable } from "@shared/components/skeleton";
import { formatDate } from "@shared/lib/format";
import type { BillingCycle, CycleStatus } from "@shared/types/billing";

const STATUS_BADGES: Record<CycleStatus, { label: string; className: string }> = {
  draft: { label: "Draft", className: "bg-slate-700 text-slate-300" },
  validating: { label: "Validating", className: "bg-blue-500/20 text-blue-300" },
  pending_approval: { label: "Pending Approval", className: "bg-yellow-500/20 text-yellow-300" },
  approved: { label: "Approved", className: "bg-teal-500/20 text-teal-300" },
  generating: { label: "Generating", className: "bg-purple-500/20 text-purple-300" },
  completed: { label: "Completed", className: "bg-green-500/20 text-green-300" },
  voided: { label: "Voided", className: "bg-red-500/20 text-red-300" },
};

function StatusBadge({ status }: { status: CycleStatus }) {
  const badge = STATUS_BADGES[status] ?? { label: status, className: "bg-slate-700 text-slate-300" };
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${badge.className}`}>
      {badge.label}
    </span>
  );
}

const columns: ColDef<BillingCycle>[] = [
  { accessorKey: "cycle_period", header: "Period", size: 100 },
  { accessorKey: "client_name", header: "Client", size: 160 },
  { accessorKey: "program_name", header: "Program", size: 140 },
  {
    accessorKey: "total_claims",
    header: "Claims",
    cell: ({ row }) => (
      <span className="tabular-nums">{row.original.total_claims.toLocaleString()}</span>
    ),
    size: 90,
  },
  {
    accessorKey: "total_ap_amount",
    header: "AP Total",
    cell: ({ row }) => <DollarCell amount={row.original.total_ap_amount} />,
    size: 130,
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ row }) => <StatusBadge status={row.original.status} />,
    size: 140,
  },
  {
    accessorKey: "created_at",
    header: "Created",
    cell: ({ row }) => formatDate(row.original.created_at),
    size: 110,
  },
];

function BillingCyclesTable() {
  const router = useRouter();
  const { data, isLoading, refetch } = useQuery({
    queryKey: ["billing-cycles"],
    queryFn: () => listCycles({ page_size: 100 }),
    staleTime: 30_000,
  });

  const cycles = data?.data ?? [];

  const handleExportCsv = () => {
    const rows = cycles.map((c) => [
      c.cycle_period,
      c.client_name,
      c.program_name,
      c.total_claims,
      c.total_ap_amount,
      c.status,
      c.created_at,
    ]);
    const header = "Period,Client,Program,Claims,AP Total,Status,Created\n";
    const csv = header + rows.map((r) => r.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "billing-cycles.csv";
    a.click();
  };

  if (isLoading) return <SkeletonTable rows={6} cols={7} />;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <h2 className="text-base font-semibold text-slate-200">Active Billing Cycles</h2>
          <button
            onClick={() => refetch()}
            className="p-1.5 rounded hover:bg-navy-700 text-slate-400"
            aria-label="Refresh cycles"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
        <ExportMenu onExportCsv={handleExportCsv} />
      </div>
      <DataTable
        columns={columns}
        data={cycles}
        onRowClick={(row) => router.push(`/billing/cycles/${row.id}`)}
        emptyTitle="No billing cycles yet"
        emptyDescription="Start your first billing cycle to see claims, payments, and invoices here."
        stickyHeader
      />
    </div>
  );
}

export default function BillingPage() {
  const router = useRouter();

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Billing</h1>
          <p className="text-sm text-slate-400 mt-0.5">
            Manage billing cycles, claims, and invoices.
          </p>
        </div>
        <button
          onClick={() => router.push("/billing/cycles/new")}
          className="flex items-center gap-2 px-4 py-2 rounded-md bg-teal-500 text-white text-sm font-semibold hover:bg-teal-600 transition-colors"
        >
          <Plus className="w-4 h-4" />
          New Billing Cycle
        </button>
      </div>

      {/* Nav tabs */}
      <div className="flex gap-4 border-b border-ifx-border-dark text-sm">
        {[
          { label: "Cycles", href: "/billing" },
          { label: "Claims", href: "/billing/claims" },
          { label: "Invoices", href: "/billing/invoices" },
        ].map((tab) => (
          <button
            key={tab.href}
            onClick={() => router.push(tab.href)}
            className="pb-2 px-1 border-b-2 border-transparent text-slate-400 hover:text-slate-200 hover:border-teal-500/50 transition-colors data-[active]:border-teal-500 data-[active]:text-teal-400"
          >
            {tab.label}
          </button>
        ))}
      </div>

      <ErrorBoundary>
        <BillingCyclesTable />
      </ErrorBoundary>
    </div>
  );
}
