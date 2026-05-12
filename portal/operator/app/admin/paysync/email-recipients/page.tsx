"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Mail, Loader2, Plus } from "lucide-react";

import { ApiClientError } from "@shared/lib/api-client";
import {
  listEmailRecipients, upsertEmailRecipient,
  type EmailRecipient,
} from "@shared/lib/paysync-api";

export default function EmailRecipientsPage() {
  const [rows, setRows] = useState<EmailRecipient[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);

  function refresh() {
    setLoading(true);
    listEmailRecipients()
      .then(setRows)
      .catch((e: unknown) => {
        const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
        toast.error(`Failed to load recipients — ${msg}`);
      })
      .finally(() => setLoading(false));
  }
  useEffect(() => { refresh(); }, []);

  return (
    <div className="mx-auto max-w-[1100px] p-6">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="rounded-md bg-sky-500/10 p-2">
            <Mail className="h-5 w-5 text-sky-500" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Email recipients</h1>
            <p className="text-sm text-muted-foreground">
              Per-bill-to recipient list with primary + cc flags. Used by
              invoice send + reminder emails.
            </p>
          </div>
        </div>
        <button onClick={() => setShowAdd(true)}
                className="inline-flex items-center gap-1.5 rounded-md bg-sky-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-sky-600">
          <Plus className="h-3.5 w-3.5" /> Add recipient
        </button>
      </div>

      {loading ? <p className="text-sm text-muted-foreground">Loading…</p>
        : rows.length === 0
        ? <div className="rounded-md border border-dashed p-8 text-center text-sm text-muted-foreground">
            No recipients configured.
          </div>
        : (
          <div className="rounded-lg border bg-card">
            <table className="w-full text-sm">
              <thead className="bg-muted/30 text-xs uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 text-left">Bill-to</th>
                  <th className="px-3 py-2 text-left">Email</th>
                  <th className="px-3 py-2 text-left">Name</th>
                  <th className="px-3 py-2 text-center">Primary</th>
                  <th className="px-3 py-2 text-center">CC</th>
                  <th className="px-3 py-2 text-left">Effective</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td className="px-3 py-1.5 text-xs">
                      {r.bill_to_scope_type}/<span className="font-mono">{r.bill_to_id.slice(0, 8)}</span>
                    </td>
                    <td className="px-3 py-1.5 font-mono text-xs">{r.email_address}</td>
                    <td className="px-3 py-1.5 text-xs">{r.recipient_name ?? "—"}</td>
                    <td className="px-3 py-1.5 text-center text-xs">{r.is_primary ? "✓" : ""}</td>
                    <td className="px-3 py-1.5 text-center text-xs">{r.is_cc ? "✓" : ""}</td>
                    <td className="px-3 py-1.5 text-xs">
                      {r.effective_from}
                      {r.termination_date && <span className="text-muted-foreground"> → {r.termination_date}</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

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
  const [scopeType, setScopeType] = useState("client");
  const [billToId, setBillToId] = useState("");
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [isPrimary, setIsPrimary] = useState(true);
  const [isCc, setIsCc] = useState(false);
  const [effectiveFrom, setEffectiveFrom] = useState(new Date().toISOString().slice(0, 10));
  const [busy, setBusy] = useState(false);

  async function handleSave() {
    if (!email.trim() || !billToId.trim()) return;
    setBusy(true);
    try {
      await upsertEmailRecipient({
        bill_to_scope_type: scopeType,
        bill_to_id: billToId.trim(),
        email_address: email.trim(),
        recipient_name: name.trim() || null,
        is_primary: isPrimary,
        is_cc: isCc,
        effective_from: effectiveFrom,
      });
      toast.success("Recipient added.");
      onCreated();
    } catch (e) {
      const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
      toast.error(`Add failed — ${msg}`);
    } finally { setBusy(false); }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm"
         onClick={onClose}>
      <div className="w-full max-w-md rounded-lg border bg-card p-6 shadow-lg"
           onClick={(e) => e.stopPropagation()}>
        <h3 className="mb-3 text-base font-semibold">Add email recipient</h3>
        <div className="mb-3 grid grid-cols-2 gap-3 text-xs">
          <label>
            <span className="font-medium">Scope</span>
            <select value={scopeType} onChange={(e) => setScopeType(e.target.value)}
                    className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm">
              <option value="client">Client</option>
              <option value="program">Program</option>
              <option value="manufacturer">Manufacturer</option>
              <option value="pharmacy">Pharmacy</option>
            </select>
          </label>
          <label>
            <span className="font-medium">Bill-to ID</span>
            <input type="text" value={billToId} onChange={(e) => setBillToId(e.target.value)}
                   className="mt-1 w-full rounded-md border bg-background px-3 py-2 font-mono text-sm" />
          </label>
        </div>
        <label className="mb-3 block text-xs">
          <span className="font-medium">Email address</span>
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                 className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm" />
        </label>
        <label className="mb-3 block text-xs">
          <span className="font-medium">Recipient name (optional)</span>
          <input type="text" value={name} onChange={(e) => setName(e.target.value)}
                 className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm" />
        </label>
        <div className="mb-3 flex gap-3 text-sm">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={isPrimary}
                   onChange={(e) => setIsPrimary(e.target.checked)} />
            <span>Primary (To:)</span>
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={isCc}
                   onChange={(e) => setIsCc(e.target.checked)} />
            <span>CC</span>
          </label>
        </div>
        <label className="mb-3 block text-xs">
          <span className="font-medium">Effective from</span>
          <input type="date" value={effectiveFrom}
                 onChange={(e) => setEffectiveFrom(e.target.value)}
                 className="mt-1 rounded-md border bg-background px-3 py-2 text-sm" />
        </label>
        <div className="mt-4 flex justify-end gap-2">
          <button onClick={onClose} disabled={busy}
                  className="rounded-md border px-3 py-1.5 text-sm hover:bg-muted disabled:opacity-50">
            Cancel
          </button>
          <button onClick={handleSave} disabled={busy || !email.trim() || !billToId.trim()}
                  className="inline-flex items-center gap-1.5 rounded-md bg-sky-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-sky-600 disabled:opacity-50">
            {busy && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            Add
          </button>
        </div>
      </div>
    </div>
  );
}
