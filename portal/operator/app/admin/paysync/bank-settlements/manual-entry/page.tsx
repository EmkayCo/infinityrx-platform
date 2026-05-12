"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { ArrowLeft, Banknote, CheckCircle2, Loader2, Plus, Trash2 } from "lucide-react";

import { ApiClientError } from "@shared/lib/api-client";
import {
  createManualSettlement, type ManualSettlementRequest,
} from "@shared/lib/paysync-api";

interface EntryRow {
  trace_number: string;
  settled_amount: string;
  returned: boolean;
  return_reason_code?: string;
}

export default function ManualSettlementEntryPage() {
  const router = useRouter();
  const [settlementDate, setSettlementDate] = useState(new Date().toISOString().slice(0, 10));
  const [bankReference, setBankReference] = useState("");
  const [paymentBatchId, setPaymentBatchId] = useState("");
  const [entries, setEntries] = useState<EntryRow[]>([
    { trace_number: "", settled_amount: "0.00", returned: false },
  ]);
  const [busy, setBusy] = useState(false);

  function addEntry() {
    setEntries([...entries, { trace_number: "", settled_amount: "0.00", returned: false }]);
  }
  function updateEntry(i: number, patch: Partial<EntryRow>) {
    setEntries(entries.map((e, idx) => idx === i ? { ...e, ...patch } : e));
  }
  function removeEntry(i: number) {
    setEntries(entries.filter((_, idx) => idx !== i));
  }

  async function handleSubmit() {
    if (!bankReference.trim() || entries.length === 0) return;
    const req: ManualSettlementRequest = {
      settlement_date: settlementDate,
      bank_reference: bankReference.trim(),
      payment_batch_id: paymentBatchId.trim() || undefined,
      entries: entries.map((e) => ({
        trace_number: e.trace_number,
        settled_amount: e.settled_amount,
        returned: e.returned,
        return_reason_code: e.returned ? (e.return_reason_code ?? "R01") : undefined,
      })),
    };
    setBusy(true);
    try {
      const created = await createManualSettlement(req);
      toast.success("Settlement created.");
      router.push(`/admin/paysync/bank-settlements/${created.id}`);
    } catch (e) {
      const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
      toast.error(`Submit failed — ${msg}`);
    } finally { setBusy(false); }
  }

  const totalAmount = entries.reduce((sum, e) =>
    sum + (e.returned ? 0 : Number(e.settled_amount || 0)), 0);

  return (
    <div className="mx-auto max-w-3xl p-6">
      <div className="mb-4 flex items-center gap-2 text-sm text-muted-foreground">
        <Link href="/admin/paysync/bank-settlements"
              className="inline-flex items-center gap-1 hover:text-foreground">
          <ArrowLeft className="h-3.5 w-3.5" /> Settlements
        </Link>
        <span>/</span>
        <span className="text-foreground">Manual entry</span>
      </div>

      <header className="mb-6 flex items-start gap-3">
        <div className="rounded-md bg-emerald-500/10 p-2">
          <Banknote className="h-5 w-5 text-emerald-500" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">Manual settlement entry</h1>
          <p className="text-sm text-muted-foreground">
            Operator-keyed settlement record. Returned entries auto-create
            we_owe_pharmacy carryovers in the next cycle.
          </p>
        </div>
      </header>

      <section className="rounded-lg border bg-card p-4">
        <div className="mb-4 grid grid-cols-2 gap-3 text-xs">
          <label>
            <span className="font-medium">Settlement date</span>
            <input type="date" value={settlementDate}
                   onChange={(e) => setSettlementDate(e.target.value)}
                   className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm" />
          </label>
          <label>
            <span className="font-medium">Bank reference</span>
            <input type="text" value={bankReference}
                   onChange={(e) => setBankReference(e.target.value)}
                   placeholder="e.g. STMT-2026-04-26-0001"
                   className="mt-1 w-full rounded-md border bg-background px-3 py-2 font-mono text-sm" />
          </label>
          <label className="col-span-2">
            <span className="font-medium">Payment batch ID (optional)</span>
            <input type="text" value={paymentBatchId}
                   onChange={(e) => setPaymentBatchId(e.target.value)}
                   placeholder="UUID — link to specific batch for matching"
                   className="mt-1 w-full rounded-md border bg-background px-3 py-2 font-mono text-sm" />
          </label>
        </div>

        <h2 className="mb-2 text-sm font-semibold">Entries</h2>
        <div className="space-y-2">
          {entries.map((e, i) => (
            <div key={i} className="grid grid-cols-12 items-end gap-2 rounded-md border bg-muted/20 p-2 text-xs">
              <label className="col-span-4">
                <span className="font-medium">Trace number</span>
                <input type="text" value={e.trace_number}
                       onChange={(ev) => updateEntry(i, { trace_number: ev.target.value })}
                       className="mt-1 w-full rounded-md border bg-background px-2 py-1.5 font-mono text-xs" />
              </label>
              <label className="col-span-2">
                <span className="font-medium">Amount</span>
                <input type="text" value={e.settled_amount}
                       onChange={(ev) => updateEntry(i, { settled_amount: ev.target.value })}
                       className="mt-1 w-full rounded-md border bg-background px-2 py-1.5 font-mono text-xs" />
              </label>
              <label className="col-span-2 flex flex-col items-start">
                <span className="font-medium">Returned</span>
                <input type="checkbox" checked={e.returned}
                       onChange={(ev) => updateEntry(i, { returned: ev.target.checked })}
                       className="mt-2" />
              </label>
              <label className="col-span-3">
                <span className="font-medium">R-code</span>
                <select value={e.return_reason_code ?? ""}
                        onChange={(ev) => updateEntry(i, { return_reason_code: ev.target.value })}
                        disabled={!e.returned}
                        className="mt-1 w-full rounded-md border bg-background px-2 py-1.5 font-mono text-xs disabled:opacity-30">
                  <option value="">—</option>
                  {["R01","R02","R03","R04","R05","R06","R07","R08","R09","R10","R11","R12","R13","R14","R15","R16","R17","R18","R19","R20","R21","R22","R23","R24","R25","R26","R27","R28","R29","R30","R31"].map((c) =>
                    <option key={c} value={c}>{c}</option>)}
                </select>
              </label>
              <button onClick={() => removeEntry(i)} disabled={entries.length === 1}
                      aria-label="Remove entry"
                      className="col-span-1 rounded-md border border-rose-500/50 p-2 text-rose-600 hover:bg-rose-500/5 disabled:opacity-30">
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>

        <button onClick={addEntry}
                className="mt-3 inline-flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-sm hover:bg-muted">
          <Plus className="h-3.5 w-3.5" /> Add entry
        </button>

        <div className="mt-6 flex items-center justify-between border-t pt-4">
          <p className="text-xs text-muted-foreground">
            Net (excl. returned): <span className="font-mono">${totalAmount.toFixed(2)}</span>
            {" · "}{entries.filter(e => e.returned).length} returned
          </p>
          <button onClick={handleSubmit} disabled={busy || !bankReference.trim()}
                  className="inline-flex items-center gap-1.5 rounded-md bg-emerald-500 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-600 disabled:opacity-50">
            {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  : <CheckCircle2 className="h-3.5 w-3.5" />}
            Create settlement
          </button>
        </div>
      </section>
    </div>
  );
}
