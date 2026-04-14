// Payments landing page — batch DataTable + "New Batch" button.
"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { Plus, RefreshCw } from "lucide-react";
import { listBatches } from "@shared/lib/payments-api";
import { DataTable, type ColDef } from "@shared/components/data-table";
import { DollarCell } from "@shared/components/dollar-display";
import { ExportMenu } from "@shared/components/export-menu";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { SkeletonTable } from "@shared/components/skeleton";
import { formatDateTime } from "@shared/lib/format";
import type { PaymentBatch, BatchStatus } from "@shared/types/payments";

const STATUS_CLASSES: Record<BatchStatus, string> = {
  draft: "bg-slate-700 text-slate-300",
  pending_approval: "bg-yellow-500/20 text-yellow-300",
  approved: "bg-teal-500/20 text-teal-300",
  generating: "bg-purple-500/20 text-purple-300",
  generated: "bg-blue-500/20 text-blue-300",
  transmitting: "bg-orange-500/20 text-orange-300",
  transmitted: "bg-teal-600/20 text-teal-400",
  acknowledged: "bg-green-500/20 text-green-300",
  settled: "bg-green-700/20 text-green-400",
  failed: "bg-red-500/20 text-red-400",
  voided: "bg-slate-700 text-slate-500",
};

const columns: ColDef<PaymentBatch>[] = [
  { accessorKey: "id", header: "Batch ID", size: 180, cell: ({ row }) => (
    <span className="font-mono text-xs text-slate-400">{row.original.id.slice(0, 8)}…</span>
  )},
  {
    accessorKey: "status",
    header: "Status",
    cell: ({ row }) => (
      <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_CLASSES[row.original.status] ?? "bg-slate-700 text-slate-300"}`}>
        {row.original.status.replace(/_/g, " ")}
      </span>
    ),
    size: 140,
  },
  { accessorKey: "vendor_name", header: "Vendor", size: 140 },
  {
    accessorKey: "payment_count",
    header: "Payments",
    cell: ({ row }) => (
      <span className="tabular-nums">{row.original.payment_count.toLocaleString()}</span>
    ),
    size: 90,
  },
  {
    accessorKey: "total_amount",
    header: "Total",
    cell: ({ row }) => <DollarCell amount={row.original.total_amount} />,
    size: 130,
  },
  {
    accessorKey: "transmitted_at",
    header: "Transmitted",
    cell: ({ row }) => formatDateTime(row.original.transmitted_at),
    size: 160,
  },
  {
    accessorKey: "ack_status",
    header: "Ack",
    cell: ({ row }) => {
      const ack = row.original.ack_status;
      if (!ack) return <span className="text-slate-600">—</span>;
      return (
        <span className={
          ack === "acknowledged" ? "text-green-400 text-xs" :
          ack === "rejected" ? "text-red-400 text-xs" :
          "text-yellow-400 text-xs"
        }>
          {ack}
        </span>
      );
    },
    size: 110,
  },
];

export default function PaymentsPage() {
  const router = useRouter();

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["payment-batches"],
    queryFn: () => listBatches({ page_size: 100 }),
    staleTime: 15_000,
  });

  const batches = data?.data ?? [];

  const handleExportCsv = () => {
    const rows = batches.map((b) => [
      b.id,
      b.status,
      b.vendor_name,
      b.payment_count,
      b.total_amount,
      b.transmitted_at ?? "",
      b.ack_status ?? "",
    ]);
    const csv =
      "ID,Status,Vendor,Payments,Total,Transmitted,Ack\n" +
      rows.map((r) => r.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "payment-batches.csv";
    a.click();
  };

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Payments</h1>
          <p className="text-sm text-slate-400 mt-0.5">
            Manage payment batches, NACHA files, and vendor transmissions.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => refetch()}
            className="p-2 rounded hover:bg-navy-700 text-slate-400"
            aria-label="Refresh"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
          <button
            onClick={() => router.push("/payments/batches/new")}
            className="flex items-center gap-2 px-4 py-2 rounded-md bg-teal-500 text-white text-sm font-semibold hover:bg-teal-600 transition-colors"
          >
            <Plus className="w-4 h-4" />
            New Batch
          </button>
        </div>
      </div>

      {/* Nav tabs */}
      <div className="flex gap-4 border-b border-ifx-border-dark text-sm">
        {[
          { label: "Batches", href: "/payments" },
          { label: "NACHA Files", href: "/payments/nacha" },
        ].map((tab) => (
          <button
            key={tab.href}
            onClick={() => router.push(tab.href)}
            className="pb-2 px-1 border-b-2 border-transparent text-slate-400 hover:text-slate-200 hover:border-teal-500/50 transition-colors"
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-300">Payment Batches</h2>
        <ExportMenu onExportCsv={handleExportCsv} />
      </div>

      <ErrorBoundary>
        {isLoading ? (
          <SkeletonTable rows={6} cols={7} />
        ) : (
          <DataTable
            columns={columns}
            data={batches}
            onRowClick={(row) => router.push(`/payments/batches/${row.id}`)}
            emptyTitle="No payment batches"
            emptyDescription="Create your first payment batch to send ACH payments to pharmacies."
            stickyHeader
          />
        )}
      </ErrorBoundary>
    </div>
  );
}
