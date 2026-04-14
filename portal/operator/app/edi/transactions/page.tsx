"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { DataTable, type ColDef } from "@shared/components/data-table";
import { ExportMenu } from "@shared/components/export-menu";
import { apiGet, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import type { EDITransaction, TransactionType, TransactionDirection, TransactionStatus } from "@shared/types/edi";
import { cn, formatDateTime } from "@shared/lib/format";
import { useRouter } from "next/navigation";

const STATUS_BADGE: Record<TransactionStatus, string> = {
  accepted: "bg-green-900/40 text-green-300",
  rejected: "bg-red-900/40 text-red-300",
  pending: "bg-yellow-900/40 text-yellow-300",
  acknowledged: "bg-blue-900/40 text-blue-300",
  error: "bg-red-900/40 text-red-400",
};

const DIRECTION_BADGE: Record<TransactionDirection, string> = {
  inbound: "bg-teal-900/40 text-teal-300",
  outbound: "bg-purple-900/40 text-purple-300",
};

const TX_TYPES: TransactionType[] = ["835", "837", "270", "271", "276", "277", "278", "834", "999"];

const columns: ColDef<EDITransaction>[] = [
  {
    accessorKey: "filename",
    header: "Filename",
    cell: (c) => <span className="font-mono text-xs text-white">{c.getValue() as string}</span>,
  },
  {
    accessorKey: "direction",
    header: "Direction",
    cell: (c) => (
      <span className={cn("text-xs px-2 py-0.5 rounded capitalize", DIRECTION_BADGE[c.getValue() as TransactionDirection])}>
        {c.getValue() as string}
      </span>
    ),
  },
  {
    accessorKey: "transaction_type",
    header: "Type",
    cell: (c) => (
      <span className="text-xs px-2 py-0.5 rounded bg-navy-700 text-slate-300 font-mono">
        {c.getValue() as string}
      </span>
    ),
  },
  {
    accessorKey: "partner_name",
    header: "Partner",
    cell: (c) => <span className="text-slate-300 text-sm">{c.getValue() as string}</span>,
  },
  {
    accessorKey: "received_at",
    header: "Received",
    cell: (c) => <span className="text-xs text-slate-400">{formatDateTime(c.getValue() as string)}</span>,
  },
  {
    accessorKey: "transaction_count",
    header: "Transactions",
    cell: (c) => <span className="text-slate-300">{c.getValue() as number}</span>,
  },
  {
    accessorKey: "status",
    header: "Status",
    cell: (c) => (
      <span className={cn("text-xs px-2 py-0.5 rounded capitalize", STATUS_BADGE[c.getValue() as TransactionStatus])}>
        {c.getValue() as string}
      </span>
    ),
  },
];

export default function TransactionsPage() {
  const router = useRouter();
  const [typeFilter, setTypeFilter] = useState<TransactionType | "all">("all");
  const [directionFilter, setDirectionFilter] = useState<TransactionDirection | "all">("all");
  const [statusFilter, setStatusFilter] = useState<TransactionStatus | "all">("all");

  const { data: transactions = [], isLoading } = useQuery<EDITransaction[]>({
    queryKey: ["edi-transactions", typeFilter, directionFilter, statusFilter],
    queryFn: () =>
      apiGet<EDITransaction[]>(
        buildUrl(`${API_URLS.edi}/api/v1/transactions`, {
          type: typeFilter !== "all" ? typeFilter : undefined,
          direction: directionFilter !== "all" ? directionFilter : undefined,
          status: statusFilter !== "all" ? statusFilter : undefined,
          limit: 100,
        })
      ),
    staleTime: 30_000,
  });

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Transaction Browser</h1>
          <p className="text-slate-400 text-sm mt-1">{transactions.length} transactions</p>
        </div>
        <ExportMenu onExportCsv={() => {/* export */}} />
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <label className="text-xs text-slate-400">Type:</label>
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value as TransactionType | "all")}
            className="px-2 py-1.5 rounded-lg border border-ifx-border-dark bg-ifx-surface-dark text-white text-xs focus:outline-none"
          >
            <option value="all">All Types</option>
            {TX_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs text-slate-400">Direction:</label>
          <select
            value={directionFilter}
            onChange={(e) => setDirectionFilter(e.target.value as TransactionDirection | "all")}
            className="px-2 py-1.5 rounded-lg border border-ifx-border-dark bg-ifx-surface-dark text-white text-xs focus:outline-none"
          >
            <option value="all">All</option>
            <option value="inbound">Inbound</option>
            <option value="outbound">Outbound</option>
          </select>
        </div>
        <div className="flex items-center gap-2">
          <label className="text-xs text-slate-400">Status:</label>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as TransactionStatus | "all")}
            className="px-2 py-1.5 rounded-lg border border-ifx-border-dark bg-ifx-surface-dark text-white text-xs focus:outline-none"
          >
            <option value="all">All</option>
            {(["accepted", "rejected", "pending", "acknowledged", "error"] as TransactionStatus[]).map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>
      </div>

      <ErrorBoundary>
        <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
          <DataTable
            columns={columns}
            data={transactions}
            isLoading={isLoading}
            emptyTitle="No transactions found"
            emptyDescription="Adjust filters to find transactions."
            onRowClick={(r: EDITransaction) => router.push(`/edi/transactions/${r.id}`)}
          />
        </div>
      </ErrorBoundary>
    </div>
  );
}
