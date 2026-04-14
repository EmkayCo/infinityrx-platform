// Invoice Management page.
"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { listInvoices } from "@shared/lib/billing-api";
import { DataTable, type ColDef } from "@shared/components/data-table";
import { DollarCell } from "@shared/components/dollar-display";
import { ExportMenu } from "@shared/components/export-menu";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { SkeletonTable } from "@shared/components/skeleton";
import { formatDate } from "@shared/lib/format";
import type { Invoice, InvoiceStatus } from "@shared/types/billing";

const STATUS_CLASSES: Record<InvoiceStatus, string> = {
  generated: "bg-blue-500/20 text-blue-300",
  sent: "bg-teal-500/20 text-teal-300",
  paid: "bg-green-500/20 text-green-300",
  overdue: "bg-red-500/20 text-red-400",
  voided: "bg-slate-700 text-slate-500",
};

const columns: ColDef<Invoice>[] = [
  { accessorKey: "invoice_number", header: "Invoice #", size: 130 },
  { accessorKey: "client_name", header: "Client", size: 160 },
  {
    accessorKey: "total_amount",
    header: "Amount",
    cell: ({ row }) => <DollarCell amount={row.original.total_amount} />,
    size: 120,
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
    size: 110,
  },
  {
    accessorKey: "issued_at",
    header: "Issued",
    cell: ({ row }) => formatDate(row.original.issued_at),
    size: 110,
  },
  {
    accessorKey: "due_date",
    header: "Due",
    cell: ({ row }) => formatDate(row.original.due_date),
    size: 110,
  },
  {
    accessorKey: "paid_at",
    header: "Paid",
    cell: ({ row }) => formatDate(row.original.paid_at),
    size: 110,
  },
];

export default function InvoicesPage() {
  const router = useRouter();
  const [statusFilter, setStatusFilter] = React.useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["invoices", statusFilter],
    queryFn: () =>
      listInvoices({
        status: statusFilter || undefined,
        page_size: 100,
      }),
    staleTime: 30_000,
  });

  const invoices = data?.data ?? [];

  const handleExportCsv = () => {
    const rows = invoices.map((i) => [
      i.invoice_number,
      i.client_name,
      i.total_amount,
      i.status,
      i.issued_at ?? "",
      i.due_date,
      i.paid_at ?? "",
    ]);
    const csv =
      "Invoice #,Client,Amount,Status,Issued,Due,Paid\n" +
      rows.map((r) => r.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "invoices.csv";
    a.click();
  };

  return (
    <div className="p-6 space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-slate-100">Invoice Management</h1>
        <ExportMenu onExportCsv={handleExportCsv} />
      </div>

      {/* Status filter */}
      <select
        value={statusFilter}
        onChange={(e) => setStatusFilter(e.target.value)}
        className="px-3 py-1.5 text-sm rounded-md border border-ifx-border-dark bg-navy-900 text-white focus:outline-none focus:ring-2 focus:ring-teal-500/40"
        aria-label="Filter by invoice status"
      >
        <option value="">All statuses</option>
        {(["generated", "sent", "paid", "overdue", "voided"] as InvoiceStatus[]).map(
          (s) => (
            <option key={s} value={s}>
              {s.charAt(0).toUpperCase() + s.slice(1)}
            </option>
          )
        )}
      </select>

      <ErrorBoundary>
        {isLoading ? (
          <SkeletonTable rows={6} cols={7} />
        ) : (
          <DataTable
            columns={columns}
            data={invoices}
            onRowClick={(row) => router.push(`/billing/invoices/${row.id}`)}
            emptyTitle="No invoices found"
            emptyDescription="No invoices match the current filters."
            stickyHeader
          />
        )}
      </ErrorBoundary>
    </div>
  );
}
