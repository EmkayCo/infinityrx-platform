"use client";

// Cycles list — Wave 40 M1.
//
// Server-side paginated table of cycles with filters. Top-level
// entry point for paysync operators: open cycles surface here, and
// quick actions drill into close wizard or detail view.

import { useEffect, useState, useMemo } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { toast } from "sonner";
import { Calendar, FileText, RefreshCw, Plus } from "lucide-react";

import { ApiClientError } from "@shared/lib/api-client";
import {
  listCycles, type Cycle, type CycleListQuery,
  type CycleType, type CycleStatus,
} from "@shared/lib/paysync-api";

import {
  PaginatedTable, readPaginationFromUrl,
  type PaginatedColumn,
} from "@/components/paysync/paginated-table";
import { CycleStatusBadge } from "@/components/paysync/cycle-status-badge";

export default function CyclesListPage() {
  const params = useSearchParams();
  const pagination = useMemo(() => readPaginationFromUrl(params, {
    page: 1, page_size: 50, sort_by: "period_start", sort_dir: "desc",
  }), [params]);

  const cycleType = (params.get("cycle_type") as CycleType | null) ?? undefined;
  const status = (params.get("status") as CycleStatus | null) ?? undefined;
  const periodStartGte = params.get("period_start_gte") ?? undefined;
  const periodEndLte = params.get("period_end_lte") ?? undefined;

  const [rows, setRows] = useState<Cycle[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    const query: CycleListQuery = {
      ...pagination,
      cycle_type: cycleType,
      status,
      period_start_gte: periodStartGte,
      period_end_lte: periodEndLte,
    };

    listCycles(query)
      .then((page) => {
        if (cancelled) return;
        setRows(page.items);
        setTotal(page.total);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        const msg = e instanceof ApiClientError
          ? `${e.code}: ${e.message}` : String(e);
        setError(msg);
        toast.error(`Failed to load cycles — ${msg}`);
      })
      .finally(() => { if (!cancelled) setLoading(false); });

    return () => { cancelled = true; };
  }, [pagination, cycleType, status, periodStartGte, periodEndLte]);

  const columns: PaginatedColumn<Cycle>[] = [
    {
      id: "label", header: "Cycle", sortKey: "cycle_label",
      accessor: (row) => (
        <Link href={`/admin/paysync/cycles/${row.id}`}
              className="font-medium text-sky-500 hover:underline">
          {row.cycle_label}
        </Link>
      ),
    },
    {
      id: "type", header: "Type", sortKey: "cycle_type",
      accessor: (row) => (
        <span className="text-xs">
          {row.cycle_type === "payment_cycle" ? "Payment" : "Invoice"}
        </span>
      ),
    },
    {
      id: "period_start", header: "Period start", sortKey: "period_start",
      accessor: (row) => (
        <span className="font-mono text-xs">{row.period_start}</span>
      ),
    },
    {
      id: "period_end", header: "Period end", sortKey: "period_end",
      accessor: (row) => (
        <span className="font-mono text-xs">{row.period_end}</span>
      ),
    },
    {
      id: "schedule", header: "Schedule",
      accessor: (row) => (
        <span className="text-xs text-muted-foreground">
          {row.schedule_name ?? "—"}
        </span>
      ),
    },
    {
      id: "status", header: "Status", sortKey: "status",
      accessor: (row) => <CycleStatusBadge status={row.status} />,
    },
    {
      id: "claims", header: "Claims", sortKey: "claim_count",
      align: "right",
      accessor: (row) => row.claim_count.toLocaleString(),
    },
    {
      id: "total_pay", header: "Total pay", sortKey: "total_pay",
      align: "right",
      accessor: (row) => `$${Number(row.total_pay).toLocaleString(undefined, {
        minimumFractionDigits: 2, maximumFractionDigits: 2,
      })}`,
    },
    {
      id: "recon", header: "Recon",
      accessor: (row) => row.reconciliation_status ? (
        <span className="text-xs">{row.reconciliation_status}</span>
      ) : <span className="text-xs text-muted-foreground">—</span>,
    },
  ];

  return (
    <div className="mx-auto max-w-[1400px] p-6">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="rounded-md bg-teal-500/10 p-2">
            <Calendar className="h-5 w-5 text-teal-500" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Cycles</h1>
            <p className="text-sm text-muted-foreground">
              Payment + invoice cycles with status, claim counts, and
              reconciliation outcomes.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => location.reload()}
            className="inline-flex items-center gap-1.5 rounded-md border bg-background px-3 py-1.5 text-sm hover:bg-muted"
          >
            <RefreshCw className="h-3.5 w-3.5" /> Refresh
          </button>
        </div>
      </div>

      <FilterBar
        cycleType={cycleType} status={status}
        periodStartGte={periodStartGte} periodEndLte={periodEndLte}
      />

      <PaginatedTable<Cycle>
        columns={columns}
        rows={rows}
        total={total}
        page={pagination.page}
        pageSize={pagination.page_size}
        loading={loading}
        error={error}
        rowKey={(c) => c.id}
        emptyTitle="No cycles match the filters"
        emptyHint="Cycles open automatically per the active schedule. Check Cycle Schedules under PaySync Config."
        emptyAction={
          <Link href="/admin/paysync/cycle-schedules"
                className="inline-flex items-center gap-1.5 rounded-md bg-teal-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-teal-600">
            <Plus className="h-3.5 w-3.5" /> Manage cycle schedules
          </Link>
        }
      />
    </div>
  );
}

function FilterBar({
  cycleType, status, periodStartGte, periodEndLte,
}: {
  cycleType?: CycleType;
  status?: CycleStatus;
  periodStartGte?: string;
  periodEndLte?: string;
}) {
  const params = useSearchParams();

  function withParam(key: string, value: string | null): string {
    const next = new URLSearchParams(params.toString());
    if (!value) next.delete(key);
    else next.set(key, value);
    next.delete("page");
    return `?${next.toString()}`;
  }

  return (
    <div className="mb-4 flex flex-wrap items-end gap-3">
      <Filter label="Cycle type">
        <select
          value={cycleType ?? ""}
          onChange={(e) => {
            const v = e.target.value || null;
            location.href = withParam("cycle_type", v);
          }}
          className="rounded-md border bg-background px-2 py-1.5 text-sm"
        >
          <option value="">Any</option>
          <option value="payment_cycle">Payment</option>
          <option value="invoice_cycle">Invoice</option>
        </select>
      </Filter>
      <Filter label="Status">
        <select
          value={status ?? ""}
          onChange={(e) => {
            const v = e.target.value || null;
            location.href = withParam("status", v);
          }}
          className="rounded-md border bg-background px-2 py-1.5 text-sm"
        >
          <option value="">Any</option>
          <option value="open">Open</option>
          <option value="closing">Closing</option>
          <option value="closed">Closed</option>
          <option value="invoiced">Invoiced</option>
          <option value="paid">Paid</option>
          <option value="reconciled">Reconciled</option>
          <option value="closed_finalized">Closed (finalized)</option>
        </select>
      </Filter>
      <Filter label="Period start ≥">
        <input
          type="date" defaultValue={periodStartGte ?? ""}
          onBlur={(e) => {
            const v = e.target.value || null;
            location.href = withParam("period_start_gte", v);
          }}
          className="rounded-md border bg-background px-2 py-1.5 text-sm"
        />
      </Filter>
      <Filter label="Period end ≤">
        <input
          type="date" defaultValue={periodEndLte ?? ""}
          onBlur={(e) => {
            const v = e.target.value || null;
            location.href = withParam("period_end_lte", v);
          }}
          className="rounded-md border bg-background px-2 py-1.5 text-sm"
        />
      </Filter>
    </div>
  );
}

function Filter({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-xs">
      <span className="font-medium text-muted-foreground">{label}</span>
      {children}
    </label>
  );
}
