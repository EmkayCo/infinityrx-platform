// Step 1 — Select Claims for Payment
"use client";

import React, { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { listEligibleClaims } from "@shared/lib/payments-api";
import { DataTable, type ColDef } from "@shared/components/data-table";
import { DollarDisplay, DollarCell } from "@shared/components/dollar-display";
import { Skeleton } from "@shared/components/skeleton";
import { formatDate } from "@shared/lib/format";
import { cn } from "@shared/lib/format";
import { PaymentBatchWizardData } from "./types";
import type { Claim } from "@shared/types/billing";
import Decimal from "decimal.js";

interface SelectClaimsStepProps {
  data: PaymentBatchWizardData;
  onChange: (partial: Partial<PaymentBatchWizardData>) => void;
}

const columns: ColDef<Claim>[] = [
  {
    id: "select",
    header: ({ table }) => (
      <input
        type="checkbox"
        checked={table.getIsAllPageRowsSelected()}
        onChange={table.getToggleAllPageRowsSelectedHandler()}
        aria-label="Select all"
        className="rounded border-ifx-border-dark bg-navy-900 text-teal-500"
      />
    ),
    cell: ({ row }) => (
      <input
        type="checkbox"
        checked={row.getIsSelected()}
        onChange={row.getToggleSelectedHandler()}
        aria-label={`Select claim ${row.original.id}`}
        className="rounded border-ifx-border-dark bg-navy-900 text-teal-500"
        onClick={(e) => e.stopPropagation()}
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
];

export function SelectClaimsStep({ data, onChange }: SelectClaimsStepProps) {
  const [clientFilter, setClientFilter] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const { data: claimsData, isLoading } = useQuery({
    queryKey: ["eligible-claims", clientFilter, dateFrom, dateTo],
    queryFn: () =>
      listEligibleClaims({
        client_id: clientFilter || undefined,
        fill_date_from: dateFrom || undefined,
        fill_date_to: dateTo || undefined,
        page_size: 500,
      }),
  });

  const claims = claimsData?.data ?? [];

  // Recompute total when selection changes
  useEffect(() => {
    if (data.selected_claim_ids.length === 0) {
      onChange({ selected_total: "0.00" });
      return;
    }
    const selected = claims.filter((c) => data.selected_claim_ids.includes(c.id));
    const total = selected.reduce(
      (sum, c) => sum.plus(new Decimal(c.plan_paid)),
      new Decimal(0)
    );
    onChange({ selected_total: total.toFixed(2) });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data.selected_claim_ids, claims]);

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const handleRowSelectionChange = (selectedRows: Record<string, boolean>) => {
    const ids = Object.entries(selectedRows)
      .filter(([, v]) => v)
      .map(([id]) => id);
    onChange({ selected_claim_ids: ids });
  };

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <input
          type="text"
          placeholder="Filter by client…"
          value={clientFilter}
          onChange={(e) => setClientFilter(e.target.value)}
          className="px-3 py-1.5 text-sm rounded-md border border-ifx-border-dark bg-navy-900 text-white placeholder:text-slate-600 focus:outline-none focus:ring-2 focus:ring-teal-500/40 w-44"
        />
        <div className="flex items-center gap-2">
          <label className="text-xs text-slate-500">From</label>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="px-2 py-1.5 text-sm rounded-md border border-ifx-border-dark bg-navy-900 text-white focus:outline-none focus:ring-2 focus:ring-teal-500/40"
          />
          <label className="text-xs text-slate-500">To</label>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="px-2 py-1.5 text-sm rounded-md border border-ifx-border-dark bg-navy-900 text-white focus:outline-none focus:ring-2 focus:ring-teal-500/40"
          />
        </div>
      </div>

      {/* Table */}
      {isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : (
        <DataTable
          columns={columns}
          data={claims}
          enableRowSelection
          getRowId={(row) => row.id}
          emptyTitle="No eligible claims"
          emptyDescription="No claims are currently eligible for payment. Claims must be approved before batching."
        />
      )}

      {/* Sticky footer with running total */}
      {data.selected_claim_ids.length > 0 && (
        <div
          className={cn(
            "sticky bottom-0 rounded-lg border border-teal-500/40 bg-navy-900 p-3",
            "flex items-center justify-between"
          )}
        >
          <span className="text-sm text-slate-300">
            <span className="font-semibold text-white">
              {data.selected_claim_ids.length}
            </span>{" "}
            claim{data.selected_claim_ids.length !== 1 ? "s" : ""} selected
          </span>
          <div className="flex items-center gap-2">
            <span className="text-sm text-slate-400">Total:</span>
            <DollarDisplay amount={data.selected_total} size="lg" showScale />
          </div>
        </div>
      )}
    </div>
  );
}
