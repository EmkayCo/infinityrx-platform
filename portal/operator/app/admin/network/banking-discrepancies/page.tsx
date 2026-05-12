"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { AlertTriangle, ShieldCheck, X } from "lucide-react";

import { ApiClientError } from "@shared/lib/api-client";
import {
  listBankingDiscrepancies, resolveBankingDiscrepancy,
  type BankingDiscrepancyReview,
} from "@shared/lib/paysync-api";

import {
  PaginatedTable, readPaginationFromUrl, type PaginatedColumn,
} from "@/components/paysync/paginated-table";

export default function BankingDiscrepanciesPage() {
  const params = useSearchParams();
  const pagination = useMemo(() => readPaginationFromUrl(params, {
    page: 1, page_size: 50, sort_by: "detected_at", sort_dir: "desc",
  }), [params]);
  const status = params.get("status") ?? "pending";

  const [rows, setRows] = useState<BankingDiscrepancyReview[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [resolveOpen, setResolveOpen] = useState<BankingDiscrepancyReview | null>(null);

  function refresh() {
    setLoading(true);
    listBankingDiscrepancies({ ...pagination, status })
      .then((p) => { setRows(p.items); setTotal(p.total); })
      .catch((e: unknown) => {
        const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
        setError(msg);
        toast.error(`Failed to load discrepancies — ${msg}`);
      })
      .finally(() => setLoading(false));
  }
  useEffect(() => { refresh(); }, [pagination, status]);

  const columns: PaginatedColumn<BankingDiscrepancyReview>[] = [
    {
      id: "pay_to", header: "Pay-to",
      accessor: (row) => row.pay_to_name,
    },
    {
      id: "imported", header: "Imported",
      accessor: (row) => (
        <span className="font-mono text-xs">
          {row.imported_routing.slice(0, 5)}…/****{row.imported_account_last_four}
        </span>
      ),
    },
    {
      id: "network", header: "Network",
      accessor: (row) => (
        <span className="font-mono text-xs">
          {row.network_routing.slice(0, 5)}…/****{row.network_account_last_four}
        </span>
      ),
    },
    {
      id: "status", header: "Status", sortKey: "status",
      accessor: (row) => row.status,
    },
    {
      id: "detected", header: "Detected", sortKey: "detected_at",
      accessor: (row) => <span className="text-xs">{new Date(row.detected_at).toLocaleString()}</span>,
    },
    {
      id: "actions", header: "",
      accessor: (row) => row.status === "pending" && (
        <button onClick={() => setResolveOpen(row)}
                className="rounded-md border px-2 py-1 text-xs hover:bg-muted">
          Resolve
        </button>
      ),
    },
  ];

  return (
    <div className="mx-auto max-w-[1400px] p-6">
      <div className="mb-6 flex items-start gap-3">
        <div className="rounded-md bg-amber-500/10 p-2">
          <AlertTriangle className="h-5 w-5 text-amber-500" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">Banking discrepancies</h1>
          <p className="text-sm text-muted-foreground">
            Mismatches between imported claim banking and authoritative
            network banking. Operator decides whether to keep network as
            authoritative, accept imported, or ignore.
          </p>
        </div>
      </div>

      <PaginatedTable<BankingDiscrepancyReview>
        columns={columns} rows={rows} total={total}
        page={pagination.page} pageSize={pagination.page_size}
        loading={loading} error={error}
        rowKey={(r) => r.id}
        emptyTitle={status === "pending" ? "No pending discrepancies" : "No matches"}
      />

      {resolveOpen && (
        <ResolveDialog
          discrepancy={resolveOpen}
          onClose={() => setResolveOpen(null)}
          onResolved={() => { setResolveOpen(null); refresh(); }}
        />
      )}
    </div>
  );
}

function ResolveDialog({
  discrepancy, onClose, onResolved,
}: {
  discrepancy: BankingDiscrepancyReview;
  onClose: () => void;
  onResolved: () => void;
}) {
  const [resolution, setResolution] = useState<"keep_network" | "accept_imported" | "ignore">("keep_network");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleResolve() {
    setBusy(true);
    try {
      await resolveBankingDiscrepancy(discrepancy.id, resolution, notes || undefined);
      toast.success("Discrepancy resolved.");
      onResolved();
    } catch (e) {
      const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
      toast.error(`Resolve failed — ${msg}`);
    } finally { setBusy(false); }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm"
         onClick={onClose}>
      <div className="w-full max-w-lg rounded-lg border bg-card p-6 shadow-lg"
           onClick={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-start justify-between">
          <h3 className="text-base font-semibold">Resolve discrepancy</h3>
          <button onClick={onClose} aria-label="Close"><X className="h-4 w-4" /></button>
        </div>
        <p className="mb-3 text-sm font-medium">{discrepancy.pay_to_name}</p>
        <div className="mb-4 grid grid-cols-2 gap-3 rounded-md border bg-muted/30 p-3 text-xs">
          <div>
            <p className="font-medium text-muted-foreground">Imported (claim file)</p>
            <p className="font-mono">{discrepancy.imported_routing} / ****{discrepancy.imported_account_last_four}</p>
          </div>
          <div>
            <p className="font-medium text-muted-foreground">Network (authoritative)</p>
            <p className="font-mono">{discrepancy.network_routing} / ****{discrepancy.network_account_last_four}</p>
          </div>
        </div>
        <fieldset className="mb-3 space-y-2">
          <legend className="text-xs font-medium">Resolution</legend>
          {([
            ["keep_network", "Keep network record as authoritative", "Default. Imported value rejected."],
            ["accept_imported", "Accept imported as new authoritative", "Terminates network row, creates new active row from imported value."],
            ["ignore", "Ignore (no banking change)", "Discrepancy dismissed without affecting either record."],
          ] as const).map(([value, label, desc]) => (
            <label key={value} className="flex items-start gap-2 rounded-md border p-2 text-sm hover:bg-muted/30">
              <input type="radio" name="resolution" value={value}
                     checked={resolution === value}
                     onChange={() => setResolution(value)} />
              <div>
                <p className="font-medium">{label}</p>
                <p className="text-xs text-muted-foreground">{desc}</p>
              </div>
            </label>
          ))}
        </fieldset>
        <label className="mb-3 block text-xs">
          <span className="font-medium">Notes (optional, audit log)</span>
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2}
                    className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm" />
        </label>
        <div className="flex justify-end gap-2">
          <button onClick={onClose} disabled={busy}
                  className="rounded-md border px-3 py-1.5 text-sm hover:bg-muted disabled:opacity-50">
            Cancel
          </button>
          <button onClick={handleResolve} disabled={busy}
                  className="inline-flex items-center gap-1.5 rounded-md bg-emerald-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-600 disabled:opacity-50">
            <ShieldCheck className="h-3.5 w-3.5" /> Resolve
          </button>
        </div>
      </div>
    </div>
  );
}
