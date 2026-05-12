"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { ArrowLeftRight } from "lucide-react";

import { ApiClientError } from "@shared/lib/api-client";
import {
  listCarryovers, resolveCarryover, writeOffCarryover,
  type Carryover, type CarryoverListQuery,
  type CarryoverDirection, type CarryoverType,
} from "@shared/lib/paysync-api";

import {
  PaginatedTable, readPaginationFromUrl, type PaginatedColumn,
} from "@/components/paysync/paginated-table";
import { DestructiveActionDialog } from "@/components/paysync/destructive-action-dialog";

export default function CarryoversPage() {
  const params = useSearchParams();
  const pagination = useMemo(() => readPaginationFromUrl(params, {
    page: 1, page_size: 50, sort_by: "created_at", sort_dir: "desc",
  }), [params]);

  const carryoverType = (params.get("carryover_type") as CarryoverType | null) ?? undefined;
  const direction = (params.get("direction") as CarryoverDirection | null) ?? undefined;
  const status = params.get("status") ?? undefined;

  const [rows, setRows] = useState<Carryover[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [resolveOpen, setResolveOpen] = useState<Carryover | null>(null);
  const [writeOffOpen, setWriteOffOpen] = useState<Carryover | null>(null);
  const [writeOffReason, setWriteOffReason] = useState("");

  function refresh() {
    setLoading(true);
    const q: CarryoverListQuery = {
      ...pagination, carryover_type: carryoverType, direction, status,
    };
    listCarryovers(q)
      .then((p) => { setRows(p.items); setTotal(p.total); })
      .catch((e: unknown) => {
        const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
        setError(msg);
        toast.error(`Failed to load carryovers — ${msg}`);
      })
      .finally(() => setLoading(false));
  }
  useEffect(() => { refresh(); }, [pagination, carryoverType, direction, status]);

  async function handleWriteOff() {
    if (!writeOffOpen || !writeOffReason.trim()) return;
    try {
      await writeOffCarryover(writeOffOpen.id, writeOffReason);
      toast.success("Carryover written off.");
      setWriteOffOpen(null);
      refresh();
    } catch (e) {
      const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
      toast.error(`Write-off failed — ${msg}`);
    }
  }

  const columns: PaginatedColumn<Carryover>[] = [
    {
      id: "type", header: "Type", sortKey: "carryover_type",
      accessor: (row) => <span className="text-xs">{row.carryover_type.replace(/_/g, " ")}</span>,
    },
    {
      id: "direction", header: "Direction", sortKey: "direction",
      accessor: (row) => row.direction === "we_owe_pharmacy"
        ? <span className="text-xs text-amber-600">we owe</span>
        : <span className="text-xs text-emerald-600">pharmacy owes</span>,
    },
    {
      id: "amount", header: "Amount", sortKey: "amount", align: "right",
      accessor: (row) => `$${row.amount}`,
    },
    {
      id: "pay_to", header: "Pay-to",
      accessor: (row) => row.pay_to_external_id
        ? <span className="font-mono text-xs">{row.pay_to_external_id}</span>
        : <span className="text-xs text-muted-foreground">—</span>,
    },
    {
      id: "origin", header: "Origin",
      accessor: (row) => row.origin_cycle_id
        ? <span className="font-mono text-xs">{row.origin_cycle_id.slice(0, 8)}</span>
        : <span className="text-xs text-muted-foreground">—</span>,
    },
    {
      id: "resolution", header: "Resolution",
      accessor: (row) => row.resolution_cycle_id
        ? <span className="font-mono text-xs">{row.resolution_cycle_id.slice(0, 8)}</span>
        : <span className="text-xs text-muted-foreground">—</span>,
    },
    {
      id: "status", header: "Status", sortKey: "status",
      accessor: (row) => row.status,
    },
    {
      id: "actions", header: "",
      accessor: (row) => row.status === "open" && (
        <div className="flex justify-end gap-1">
          <button onClick={() => setResolveOpen(row)}
                  className="rounded-md border px-2 py-1 text-xs hover:bg-muted">
            Resolve
          </button>
          <button onClick={() => setWriteOffOpen(row)}
                  className="rounded-md border border-rose-500/50 px-2 py-1 text-xs text-rose-600 hover:bg-rose-500/5">
            Write off
          </button>
        </div>
      ),
    },
  ];

  return (
    <div className="mx-auto max-w-[1400px] p-6">
      <div className="mb-6 flex items-start gap-3">
        <div className="rounded-md bg-amber-500/10 p-2">
          <ArrowLeftRight className="h-5 w-5 text-amber-500" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">Carryovers</h1>
          <p className="text-sm text-muted-foreground">
            Open + resolved carryovers. We-owe entries add to next cycle
            AP; pharmacy-owes entries subtract; remainders re-roll.
          </p>
        </div>
      </div>

      <PaginatedTable<Carryover>
        columns={columns} rows={rows} total={total}
        page={pagination.page} pageSize={pagination.page_size}
        loading={loading} error={error}
        rowKey={(c) => c.id}
        emptyTitle="No carryovers match the filters"
      />

      {resolveOpen && (
        <ResolveDialog
          carryover={resolveOpen}
          onClose={() => setResolveOpen(null)}
          onResolved={() => { setResolveOpen(null); refresh(); }}
        />
      )}

      <DestructiveActionDialog
        open={!!writeOffOpen}
        onOpenChange={(o) => !o && setWriteOffOpen(null)}
        title="Write off carryover"
        description="Writing off marks the carryover settled with no
        accounting impact on future cycles. The amount remains in the
        audit log; reverse only via support."
        actionLabel="Write off"
        onConfirm={handleWriteOff}
        reasonRequired
        onReasonChange={setWriteOffReason}
      />
    </div>
  );
}

function ResolveDialog({
  carryover, onClose, onResolved,
}: {
  carryover: Carryover;
  onClose: () => void;
  onResolved: () => void;
}) {
  const [method, setMethod] = useState("next_cycle_offset");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleResolve() {
    setBusy(true);
    try {
      await resolveCarryover(carryover.id, method, notes || undefined);
      toast.success("Carryover resolved.");
      onResolved();
    } catch (e) {
      const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
      toast.error(`Resolve failed — ${msg}`);
    } finally { setBusy(false); }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm"
         onClick={onClose}>
      <div className="w-full max-w-md rounded-lg border bg-card p-6 shadow-lg"
           onClick={(e) => e.stopPropagation()}>
        <h3 className="mb-3 text-base font-semibold">Resolve carryover</h3>
        <p className="mb-3 text-xs">
          {carryover.carryover_type.replace(/_/g, " ")} ·{" "}
          {carryover.direction === "we_owe_pharmacy" ? "we owe" : "pharmacy owes"}{" "}
          ${carryover.amount}
        </p>
        <fieldset className="mb-3 space-y-2">
          <legend className="text-xs font-medium">Resolution method</legend>
          {([
            ["next_cycle_offset", "Apply to next cycle (default)"],
            ["manual_payment", "Resolved via off-cycle manual payment"],
            ["bank_chargeback", "Bank chargeback returned funds"],
          ] as const).map(([value, label]) => (
            <label key={value} className="flex items-center gap-2 rounded-md border p-2 text-sm hover:bg-muted/30">
              <input type="radio" name="method" value={value}
                     checked={method === value}
                     onChange={() => setMethod(value)} />
              <span>{label}</span>
            </label>
          ))}
        </fieldset>
        <label className="mb-3 block text-xs">
          <span className="font-medium">Notes (optional)</span>
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2}
                    className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm" />
        </label>
        <div className="mt-4 flex justify-end gap-2">
          <button onClick={onClose} disabled={busy}
                  className="rounded-md border px-3 py-1.5 text-sm hover:bg-muted disabled:opacity-50">
            Cancel
          </button>
          <button onClick={handleResolve} disabled={busy}
                  className="inline-flex items-center gap-1.5 rounded-md bg-emerald-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-600 disabled:opacity-50">
            Resolve
          </button>
        </div>
      </div>
    </div>
  );
}
