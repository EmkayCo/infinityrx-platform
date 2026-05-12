"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Receipt, Loader2 } from "lucide-react";

import { ApiClientError } from "@shared/lib/api-client";
import {
  listInvoiceSequences, setInvoiceSequenceNumber, type InvoiceSequence,
} from "@shared/lib/paysync-api";

export default function InvoiceSequencesPage() {
  const [rows, setRows] = useState<InvoiceSequence[]>([]);
  const [loading, setLoading] = useState(true);
  const [editId, setEditId] = useState<string | null>(null);

  function refresh() {
    setLoading(true);
    listInvoiceSequences()
      .then(setRows)
      .catch((e: unknown) => {
        const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
        toast.error(`Failed to load sequences — ${msg}`);
      })
      .finally(() => setLoading(false));
  }
  useEffect(() => { refresh(); }, []);

  return (
    <div className="mx-auto max-w-[1100px] p-6">
      <div className="mb-6 flex items-start gap-3">
        <div className="rounded-md bg-sky-500/10 p-2">
          <Receipt className="h-5 w-5 text-sky-500" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">Invoice sequences</h1>
          <p className="text-sm text-muted-foreground">
            Per-tenant + scope sequences (reimbursement / client_fees).
            Override next_invoice_number requires a reason; decrements
            require force_decrement.
          </p>
        </div>
      </div>

      {loading ? <p className="text-sm text-muted-foreground">Loading…</p>
        : rows.length === 0
        ? <div className="rounded-md border border-dashed p-8 text-center text-sm text-muted-foreground">
            No sequences yet. They auto-create on first allocation.
          </div>
        : (
          <div className="rounded-lg border bg-card">
            <table className="w-full text-sm">
              <thead className="bg-muted/30 text-xs uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 text-left">Type</th>
                  <th className="px-3 py-2 text-left">Scope</th>
                  <th className="px-3 py-2 text-left">Prefix</th>
                  <th className="px-3 py-2 text-right">Next #</th>
                  <th className="px-3 py-2 text-right">Started at</th>
                  <th className="px-3 py-2"></th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {rows.map((s) => (
                  <tr key={s.id}>
                    <td className="px-3 py-1.5 text-xs">{s.sequence_type}</td>
                    <td className="px-3 py-1.5 text-xs">
                      {s.scope_type}
                      {s.scope_value && <span className="ml-1 font-mono text-muted-foreground">{s.scope_value.slice(0, 8)}</span>}
                    </td>
                    <td className="px-3 py-1.5 font-mono text-xs">{s.prefix}</td>
                    <td className="px-3 py-1.5 text-right font-mono">{s.next_invoice_number}</td>
                    <td className="px-3 py-1.5 text-right font-mono text-xs">{s.starting_value}</td>
                    <td className="px-3 py-1.5 text-right">
                      <button onClick={() => setEditId(s.id)}
                              className="rounded-md border px-2 py-1 text-xs hover:bg-muted">
                        Override next #
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

      {editId && (
        <OverrideDialog sequence={rows.find((r) => r.id === editId)!}
                        onClose={() => setEditId(null)}
                        onSaved={() => { setEditId(null); refresh(); }} />
      )}
    </div>
  );
}

function OverrideDialog({
  sequence, onClose, onSaved,
}: {
  sequence: InvoiceSequence;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [next, setNext] = useState(sequence.next_invoice_number);
  const [reason, setReason] = useState("");
  const [forceDecrement, setForceDecrement] = useState(false);
  const [busy, setBusy] = useState(false);

  async function handleSave() {
    if (!reason.trim()) {
      toast.error("Reason is required.");
      return;
    }
    setBusy(true);
    try {
      await setInvoiceSequenceNumber(sequence.id, next, reason, forceDecrement);
      toast.success("Sequence number updated.");
      onSaved();
    } catch (e) {
      const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
      toast.error(`Update failed — ${msg}`);
    } finally { setBusy(false); }
  }

  const isDecrement = next < sequence.next_invoice_number;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm"
         onClick={onClose}>
      <div className="w-full max-w-md rounded-lg border bg-card p-6 shadow-lg"
           onClick={(e) => e.stopPropagation()}>
        <h3 className="mb-3 text-base font-semibold">Override sequence number</h3>
        <p className="mb-3 text-xs text-muted-foreground">
          Sequence: <span className="font-mono">{sequence.prefix}</span>{" "}
          ({sequence.sequence_type} / {sequence.scope_type})
          <br />
          Current next: <span className="font-mono">{sequence.next_invoice_number}</span>
        </p>
        <label className="mb-3 block text-xs">
          <span className="font-medium">New next number</span>
          <input type="number" value={next} min={1}
                 onChange={(e) => setNext(Number(e.target.value))}
                 className="mt-1 w-full rounded-md border bg-background px-3 py-2 font-mono text-sm" />
        </label>
        <label className="mb-3 block text-xs">
          <span className="font-medium">Reason (audit log)</span>
          <textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={3}
                    placeholder="e.g. legacy QuickBooks migration; resume at last QBO #"
                    className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm" />
        </label>
        {isDecrement && (
          <label className="mb-3 flex items-start gap-2 text-sm">
            <input type="checkbox" checked={forceDecrement}
                   onChange={(e) => setForceDecrement(e.target.checked)} />
            <span>
              Force decrement (current → smaller). Risk of duplicate invoice
              numbers.
            </span>
          </label>
        )}
        <div className="mt-4 flex justify-end gap-2">
          <button onClick={onClose} disabled={busy}
                  className="rounded-md border px-3 py-1.5 text-sm hover:bg-muted disabled:opacity-50">
            Cancel
          </button>
          <button onClick={handleSave}
                  disabled={busy || !reason.trim() || (isDecrement && !forceDecrement)}
                  className="inline-flex items-center gap-1.5 rounded-md bg-amber-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-amber-600 disabled:opacity-50">
            {busy && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            Override
          </button>
        </div>
      </div>
    </div>
  );
}
