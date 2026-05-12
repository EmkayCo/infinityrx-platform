"use client";

import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { ClipboardList, Loader2, Plus } from "lucide-react";

import { ApiClientError } from "@shared/lib/api-client";
import {
  listManualAp, createManualAp, updateManualApStatus,
  type ManualApRecord, type ManualApListQuery, type ManualApStatus,
  type CreateManualApRequest,
} from "@shared/lib/paysync-api";

import {
  PaginatedTable, readPaginationFromUrl, type PaginatedColumn,
} from "@/components/paysync/paginated-table";
import { ManualApStatusBadge } from "@/components/paysync/cycle-status-badge";

export default function ManualApPage() {
  const params = useSearchParams();
  const pagination = useMemo(() => readPaginationFromUrl(params, {
    page: 1, page_size: 50, sort_by: "created_at", sort_dir: "desc",
  }), [params]);

  const channel = params.get("channel") ?? undefined;
  const status = (params.get("status") as ManualApStatus | null) ?? undefined;
  const dateFrom = params.get("date_from") ?? undefined;
  const dateTo = params.get("date_to") ?? undefined;

  const [rows, setRows] = useState<ManualApRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAdd, setShowAdd] = useState(false);

  function refresh() {
    setLoading(true);
    const q: ManualApListQuery = {
      ...pagination, channel, status, date_from: dateFrom, date_to: dateTo,
    };
    listManualAp(q)
      .then((p) => { setRows(p.items); setTotal(p.total); })
      .catch((e: unknown) => {
        const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
        setError(msg);
        toast.error(`Failed to load manual AP — ${msg}`);
      })
      .finally(() => setLoading(false));
  }
  useEffect(() => { refresh(); }, [pagination, channel, status, dateFrom, dateTo]);

  async function handleStatusChange(id: string, newStatus: ManualApStatus) {
    let failureReason: string | undefined;
    if (newStatus === "failed") {
      const r = prompt("Failure reason (required):");
      if (!r?.trim()) return;
      failureReason = r;
    }
    try {
      await updateManualApStatus(id, newStatus, failureReason);
      toast.success(`Status updated to ${newStatus}.`);
      refresh();
    } catch (e) {
      const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
      toast.error(`Update failed — ${msg}`);
    }
  }

  const columns: PaginatedColumn<ManualApRecord>[] = [
    {
      id: "channel", header: "Channel",
      accessor: (row) => <span className="text-xs">{row.channel}</span>,
    },
    {
      id: "payee", header: "Payee",
      accessor: (row) => (
        <div className="text-xs">
          <span className="font-medium">{row.payee_name}</span>
          {row.payee_npi && <span className="ml-1 font-mono text-muted-foreground">{row.payee_npi}</span>}
        </div>
      ),
    },
    {
      id: "amount", header: "Amount", align: "right",
      accessor: (row) => `$${row.payment_amount}`,
    },
    {
      id: "ref", header: "External ref",
      accessor: (row) => row.external_reference
        ? <span className="font-mono text-xs">{row.external_reference}</span>
        : <span className="text-xs text-muted-foreground">—</span>,
    },
    {
      id: "status", header: "Status", sortKey: "status",
      accessor: (row) => <ManualApStatusBadge status={row.status} />,
    },
    {
      id: "submitted", header: "Submitted",
      accessor: (row) => row.submitted_at
        ? <span className="text-xs">{new Date(row.submitted_at).toLocaleDateString()}</span>
        : <span className="text-xs text-muted-foreground">—</span>,
    },
    {
      id: "actions", header: "",
      accessor: (row) => (
        <select value=""
                onChange={(e) => e.target.value && handleStatusChange(row.id, e.target.value as ManualApStatus)}
                className="rounded-md border bg-background px-2 py-1 text-xs">
          <option value="">change status</option>
          {row.status === "draft" && <option value="pending">→ pending</option>}
          {row.status === "pending" && <option value="recognized">→ recognized</option>}
          {row.status === "recognized" && <option value="submitted">→ submitted</option>}
          {row.status === "submitted" && <option value="processed">→ processed</option>}
          {row.status === "submitted" && <option value="failed">→ failed</option>}
          {row.status !== "voided" && row.status !== "processed" && <option value="voided">→ voided</option>}
        </select>
      ),
    },
  ];

  return (
    <div className="mx-auto max-w-[1400px] p-6">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="rounded-md bg-violet-500/10 p-2">
            <ClipboardList className="h-5 w-5 text-violet-500" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Manual AP records</h1>
            <p className="text-sm text-muted-foreground">
              Off-cycle pharmacy obligations: claims-statement
              reimbursements, rebate payments, manual corrections.
            </p>
          </div>
        </div>
        <button onClick={() => setShowAdd(true)}
                className="inline-flex items-center gap-1.5 rounded-md bg-violet-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-violet-600">
          <Plus className="h-3.5 w-3.5" /> New manual AP
        </button>
      </div>

      <PaginatedTable<ManualApRecord>
        columns={columns} rows={rows} total={total}
        page={pagination.page} pageSize={pagination.page_size}
        loading={loading} error={error}
        rowKey={(r) => r.id}
        emptyTitle="No manual AP records"
      />

      {showAdd && (
        <AddDialog onClose={() => setShowAdd(false)}
                   onCreated={() => { setShowAdd(false); refresh(); }} />
      )}
    </div>
  );
}

function AddDialog({
  onClose, onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [form, setForm] = useState<CreateManualApRequest>({
    channel: "check_issuing",
    payee_name: "",
    payment_amount: "0.00",
  });
  const [busy, setBusy] = useState(false);

  function update<K extends keyof CreateManualApRequest>(k: K, v: CreateManualApRequest[K]) {
    setForm({ ...form, [k]: v });
  }

  async function handleSave() {
    if (!form.payee_name.trim()) return;
    setBusy(true);
    try {
      await createManualAp(form);
      toast.success("Manual AP created in draft.");
      onCreated();
    } catch (e) {
      const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
      toast.error(`Create failed — ${msg}`);
    } finally { setBusy(false); }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm"
         onClick={onClose}>
      <div className="w-full max-w-md rounded-lg border bg-card p-6 shadow-lg"
           onClick={(e) => e.stopPropagation()}>
        <h3 className="mb-3 text-base font-semibold">New manual AP record</h3>
        <div className="grid gap-3 text-xs">
          <label>
            <span className="font-medium">Channel</span>
            <select value={form.channel}
                    onChange={(e) => update("channel", e.target.value)}
                    className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm">
              <option value="check_issuing">Check issuing</option>
              <option value="echo_spec_400">Echo Spec 400</option>
              <option value="manual_ach">Manual ACH</option>
              <option value="wire">Wire</option>
              <option value="adjustment">Adjustment</option>
            </select>
          </label>
          <label>
            <span className="font-medium">Payee name</span>
            <input type="text" value={form.payee_name}
                   onChange={(e) => update("payee_name", e.target.value)}
                   className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm" />
          </label>
          <label>
            <span className="font-medium">Payee NPI (optional)</span>
            <input type="text" value={form.payee_npi ?? ""}
                   onChange={(e) => update("payee_npi", e.target.value || undefined)}
                   className="mt-1 w-full rounded-md border bg-background px-3 py-2 font-mono text-sm" />
          </label>
          <label>
            <span className="font-medium">Payment amount</span>
            <input type="text" value={form.payment_amount}
                   onChange={(e) => update("payment_amount", e.target.value)}
                   className="mt-1 w-full rounded-md border bg-background px-3 py-2 font-mono text-sm" />
          </label>
          <label>
            <span className="font-medium">External reference (optional)</span>
            <input type="text" value={form.external_reference ?? ""}
                   onChange={(e) => update("external_reference", e.target.value || undefined)}
                   className="mt-1 w-full rounded-md border bg-background px-3 py-2 font-mono text-sm" />
          </label>
          <label>
            <span className="font-medium">Notes</span>
            <textarea value={form.notes ?? ""}
                      onChange={(e) => update("notes", e.target.value || undefined)}
                      rows={2}
                      className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm" />
          </label>
        </div>
        <div className="mt-4 flex justify-end gap-2">
          <button onClick={onClose} disabled={busy}
                  className="rounded-md border px-3 py-1.5 text-sm hover:bg-muted disabled:opacity-50">
            Cancel
          </button>
          <button onClick={handleSave} disabled={busy || !form.payee_name.trim()}
                  className="inline-flex items-center gap-1.5 rounded-md bg-violet-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-violet-600 disabled:opacity-50">
            {busy && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            Create draft
          </button>
        </div>
      </div>
    </div>
  );
}
