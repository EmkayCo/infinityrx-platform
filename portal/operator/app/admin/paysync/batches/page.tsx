"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { toast } from "sonner";
import { Wallet } from "lucide-react";

import { ApiClientError } from "@shared/lib/api-client";
import {
  listBatches, type PaymentBatch, type BatchListQuery, type BatchStatus,
} from "@shared/lib/paysync-api";

import {
  PaginatedTable, readPaginationFromUrl, type PaginatedColumn,
} from "@/components/paysync/paginated-table";
import { BatchStatusBadge } from "@/components/paysync/cycle-status-badge";

export default function BatchesListPage() {
  const params = useSearchParams();
  const pagination = useMemo(() => readPaginationFromUrl(params, {
    page: 1, page_size: 50, sort_by: "created_at", sort_dir: "desc",
  }), [params]);

  const cycleId = params.get("cycle_id") ?? undefined;
  const status = (params.get("status") as BatchStatus | null) ?? undefined;

  const [rows, setRows] = useState<PaymentBatch[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const q: BatchListQuery = { ...pagination, cycle_id: cycleId, status };
    listBatches(q)
      .then((p) => { if (!cancelled) { setRows(p.items); setTotal(p.total); } })
      .catch((e: unknown) => {
        const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
        if (!cancelled) { setError(msg); toast.error(`Failed to load batches — ${msg}`); }
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [pagination, cycleId, status]);

  const columns: PaginatedColumn<PaymentBatch>[] = [
    {
      id: "batch_number", header: "Batch #", sortKey: "batch_number",
      accessor: (row) => (
        <Link href={`/admin/paysync/batches/${row.id}`}
              className="font-mono text-sky-500 hover:underline">
          {row.batch_number}
        </Link>
      ),
    },
    {
      id: "cycle", header: "Cycle",
      accessor: (row) => (
        <Link href={`/admin/paysync/cycles/${row.cycle_id}`}
              className="font-mono text-xs text-muted-foreground hover:text-foreground hover:underline">
          {row.cycle_label}
        </Link>
      ),
    },
    {
      id: "status", header: "Status", sortKey: "status",
      accessor: (row) => <BatchStatusBadge status={row.status} />,
    },
    {
      id: "effective_entry", header: "Effective entry", sortKey: "effective_entry_date",
      accessor: (row) => (
        <span className="font-mono text-xs">{row.effective_entry_date}</span>
      ),
    },
    {
      id: "total", header: "Total credit", sortKey: "total_credit_amount",
      align: "right",
      accessor: (row) => `$${Number(row.total_credit_amount).toLocaleString(undefined, { minimumFractionDigits: 2 })}`,
    },
    {
      id: "credits", header: "Credits", sortKey: "credit_entry_count",
      align: "right", accessor: (row) => row.credit_entry_count,
    },
    {
      id: "claims", header: "Claims", sortKey: "claim_count",
      align: "right", accessor: (row) => row.claim_count,
    },
    {
      id: "modifier", header: "File ID",
      accessor: (row) => <span className="font-mono text-xs">{row.file_id_modifier}</span>,
    },
  ];

  return (
    <div className="mx-auto max-w-[1400px] p-6">
      <div className="mb-6 flex items-start gap-3">
        <div className="rounded-md bg-emerald-500/10 p-2">
          <Wallet className="h-5 w-5 text-emerald-500" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">Payment batches</h1>
          <p className="text-sm text-muted-foreground">
            ACH-eligible batches across all cycles. State machine:
            draft → pending_approval → approved → submitted → settled
            → reconciled.
          </p>
        </div>
      </div>

      <PaginatedTable<PaymentBatch>
        columns={columns} rows={rows} total={total}
        page={pagination.page} pageSize={pagination.page_size}
        loading={loading} error={error}
        rowKey={(b) => b.id}
        emptyTitle="No batches"
        emptyHint="Batches are generated automatically during cycle close. Run a cycle close to create the first batch."
      />
    </div>
  );
}
