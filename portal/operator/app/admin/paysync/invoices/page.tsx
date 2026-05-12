"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { toast } from "sonner";
import { Receipt } from "lucide-react";

import { ApiClientError } from "@shared/lib/api-client";
import {
  listInvoices, type Invoice, type InvoiceListQuery,
  type InvoiceStatus, type InvoiceSequenceType,
} from "@shared/lib/paysync-api";

import {
  PaginatedTable, readPaginationFromUrl, type PaginatedColumn,
} from "@/components/paysync/paginated-table";
import { InvoiceStatusBadge } from "@/components/paysync/cycle-status-badge";

export default function InvoicesListPage() {
  const params = useSearchParams();
  const pagination = useMemo(() => readPaginationFromUrl(params, {
    page: 1, page_size: 50, sort_by: "invoice_date", sort_dir: "desc",
  }), [params]);

  const cycleId = params.get("cycle_id") ?? undefined;
  const sequenceType = (params.get("sequence_type") as InvoiceSequenceType | null) ?? undefined;
  const status = (params.get("status") as InvoiceStatus | null) ?? undefined;
  const dateFrom = params.get("date_from") ?? undefined;
  const dateTo = params.get("date_to") ?? undefined;

  const [rows, setRows] = useState<Invoice[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const q: InvoiceListQuery = {
      ...pagination, cycle_id: cycleId, sequence_type: sequenceType, status,
      date_from: dateFrom, date_to: dateTo,
    };
    listInvoices(q)
      .then((p) => { if (!cancelled) { setRows(p.items); setTotal(p.total); } })
      .catch((e: unknown) => {
        const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
        if (!cancelled) { setError(msg); toast.error(`Failed to load invoices — ${msg}`); }
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [pagination, cycleId, sequenceType, status, dateFrom, dateTo]);

  const columns: PaginatedColumn<Invoice>[] = [
    {
      id: "number", header: "Invoice #", sortKey: "invoice_number",
      accessor: (row) => (
        <Link href={`/admin/paysync/invoices/${row.id}`}
              className="font-mono text-sky-500 hover:underline">
          {row.invoice_number}
        </Link>
      ),
    },
    {
      id: "type", header: "Type", sortKey: "sequence_type",
      accessor: (row) => row.sequence_type === "reimbursement" ? "Reimbursement" : "Client fees",
    },
    {
      id: "bill_to", header: "Bill to",
      accessor: (row) => row.bill_to_name,
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
      id: "date", header: "Date", sortKey: "invoice_date",
      accessor: (row) => <span className="font-mono text-xs">{row.invoice_date}</span>,
    },
    {
      id: "total", header: "Total", sortKey: "total_amount", align: "right",
      accessor: (row) => `$${Number(row.total_amount).toLocaleString(undefined, { minimumFractionDigits: 2 })}`,
    },
    {
      id: "paid", header: "Paid", sortKey: "paid_amount", align: "right",
      accessor: (row) => `$${Number(row.paid_amount).toLocaleString(undefined, { minimumFractionDigits: 2 })}`,
    },
    {
      id: "status", header: "Status", sortKey: "status",
      accessor: (row) => <InvoiceStatusBadge status={row.status} />,
    },
    {
      id: "sent", header: "Sent",
      accessor: (row) => row.sent_at
        ? <span className="text-xs">{new Date(row.sent_at).toLocaleDateString()}</span>
        : <span className="text-xs text-muted-foreground">—</span>,
    },
  ];

  return (
    <div className="mx-auto max-w-[1400px] p-6">
      <div className="mb-6 flex items-start gap-3">
        <div className="rounded-md bg-sky-500/10 p-2">
          <Receipt className="h-5 w-5 text-sky-500" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">Invoices</h1>
          <p className="text-sm text-muted-foreground">
            Reimbursement + client-fee invoices across all cycles.
          </p>
        </div>
      </div>

      <PaginatedTable<Invoice>
        columns={columns} rows={rows} total={total}
        page={pagination.page} pageSize={pagination.page_size}
        loading={loading} error={error}
        rowKey={(i) => i.id}
        emptyTitle="No invoices match the filters"
      />
    </div>
  );
}
