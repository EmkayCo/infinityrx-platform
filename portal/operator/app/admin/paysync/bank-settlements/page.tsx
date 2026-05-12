"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { toast } from "sonner";
import { Banknote, Plus } from "lucide-react";

import { ApiClientError } from "@shared/lib/api-client";
import {
  listBankSettlements, type BankSettlement, type BankSettlementListQuery,
} from "@shared/lib/paysync-api";

import {
  PaginatedTable, readPaginationFromUrl, type PaginatedColumn,
} from "@/components/paysync/paginated-table";

export default function BankSettlementsPage() {
  const params = useSearchParams();
  const pagination = useMemo(() => readPaginationFromUrl(params, {
    page: 1, page_size: 50, sort_by: "settlement_date", sort_dir: "desc",
  }), [params]);

  const source = params.get("source") ?? undefined;
  const status = params.get("status") ?? undefined;
  const dateFrom = params.get("date_from") ?? undefined;
  const dateTo = params.get("date_to") ?? undefined;

  const [rows, setRows] = useState<BankSettlement[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const q: BankSettlementListQuery = {
      ...pagination, source, status, date_from: dateFrom, date_to: dateTo,
    };
    listBankSettlements(q)
      .then((p) => { if (!cancelled) { setRows(p.items); setTotal(p.total); } })
      .catch((e: unknown) => {
        const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
        if (!cancelled) { setError(msg); toast.error(`Failed to load settlements — ${msg}`); }
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [pagination, source, status, dateFrom, dateTo]);

  const columns: PaginatedColumn<BankSettlement>[] = [
    {
      id: "settlement_date", header: "Settled", sortKey: "settlement_date",
      accessor: (row) => (
        <Link href={`/admin/paysync/bank-settlements/${row.id}`}
              className="font-mono text-sky-500 hover:underline">
          {row.settlement_date}
        </Link>
      ),
    },
    {
      id: "bank_ref", header: "Bank ref",
      accessor: (row) => <span className="font-mono text-xs">{row.bank_reference}</span>,
    },
    {
      id: "amount", header: "Amount", sortKey: "settled_amount", align: "right",
      accessor: (row) => `$${row.settled_amount}`,
    },
    {
      id: "source", header: "Source", sortKey: "source",
      accessor: (row) => row.source.replace("_", " "),
    },
    {
      id: "status", header: "Status", sortKey: "status",
      accessor: (row) => row.status,
    },
    {
      id: "bounces", header: "Bounces", align: "right",
      accessor: (row) => row.bounce_count > 0
        ? <span className="text-rose-500">{row.bounce_count}</span>
        : "0",
    },
    {
      id: "carryovers", header: "Carryovers", align: "right",
      accessor: (row) => row.carryover_count,
    },
  ];

  return (
    <div className="mx-auto max-w-[1400px] p-6">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="rounded-md bg-emerald-500/10 p-2">
            <Banknote className="h-5 w-5 text-emerald-500" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Bank settlements</h1>
            <p className="text-sm text-muted-foreground">
              ACH settlement confirmations from the bank — manual entry
              + SFTP-ingested files. Bounced entries auto-create
              we_owe_pharmacy carryovers.
            </p>
          </div>
        </div>
        <Link href="/admin/paysync/bank-settlements/manual-entry"
              className="inline-flex items-center gap-1.5 rounded-md bg-emerald-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-600">
          <Plus className="h-3.5 w-3.5" /> Manual entry
        </Link>
      </div>

      <PaginatedTable<BankSettlement>
        columns={columns} rows={rows} total={total}
        page={pagination.page} pageSize={pagination.page_size}
        loading={loading} error={error}
        rowKey={(s) => s.id}
        emptyTitle="No settlements"
        emptyHint="Settlements arrive via SFTP nightly or via manual entry."
      />
    </div>
  );
}
