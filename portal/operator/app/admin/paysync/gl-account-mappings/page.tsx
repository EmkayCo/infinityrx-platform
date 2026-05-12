"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { DollarSign, Loader2, Plus } from "lucide-react";

import { ApiClientError } from "@shared/lib/api-client";
import {
  listGlMappings, upsertGlMapping, type GlAccountMapping,
} from "@shared/lib/paysync-api";

export default function GlAccountMappingsPage() {
  const [rows, setRows] = useState<GlAccountMapping[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);

  function refresh() {
    setLoading(true);
    listGlMappings()
      .then(setRows)
      .catch((e: unknown) => {
        const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
        toast.error(`Failed to load mappings — ${msg}`);
      })
      .finally(() => setLoading(false));
  }
  useEffect(() => { refresh(); }, []);

  return (
    <div className="mx-auto max-w-[1100px] p-6">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="rounded-md bg-emerald-500/10 p-2">
            <DollarSign className="h-5 w-5 text-emerald-500" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">GL account mappings</h1>
            <p className="text-sm text-muted-foreground">
              Maps invoice line types to GL account numbers for QuickBooks
              SaaSant export. Missing mapping at SaaSant export time
              fails 422.
            </p>
          </div>
        </div>
        <button onClick={() => setShowAdd(true)}
                className="inline-flex items-center gap-1.5 rounded-md bg-emerald-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-600">
          <Plus className="h-3.5 w-3.5" /> New mapping
        </button>
      </div>

      {loading ? <p className="text-sm text-muted-foreground">Loading…</p>
        : rows.length === 0
        ? <div className="rounded-md border border-dashed p-8 text-center text-sm text-muted-foreground">
            No GL mappings configured.
          </div>
        : (
          <div className="rounded-lg border bg-card">
            <table className="w-full text-sm">
              <thead className="bg-muted/30 text-xs uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 text-left">Mapping key</th>
                  <th className="px-3 py-2 text-left">GL account</th>
                  <th className="px-3 py-2 text-left">Account name</th>
                  <th className="px-3 py-2 text-left">Effective</th>
                  <th className="px-3 py-2 text-left">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td className="px-3 py-1.5 font-mono text-xs">{r.mapping_key}</td>
                    <td className="px-3 py-1.5 font-mono text-xs">{r.gl_account}</td>
                    <td className="px-3 py-1.5 text-xs">{r.account_name ?? "—"}</td>
                    <td className="px-3 py-1.5 text-xs">
                      {r.effective_from}
                      {r.termination_date && <span className="text-muted-foreground"> → {r.termination_date}</span>}
                    </td>
                    <td className="px-3 py-1.5 text-xs">
                      {r.is_active
                        ? <span className="text-emerald-500">active</span>
                        : <span className="text-muted-foreground">inactive</span>}
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
  const [mappingKey, setMappingKey] = useState("");
  const [glAccount, setGlAccount] = useState("");
  const [accountName, setAccountName] = useState("");
  const [effectiveFrom, setEffectiveFrom] = useState(new Date().toISOString().slice(0, 10));
  const [busy, setBusy] = useState(false);

  async function handleSave() {
    if (!mappingKey.trim() || !glAccount.trim()) return;
    setBusy(true);
    try {
      await upsertGlMapping({
        mapping_key: mappingKey.trim(),
        gl_account: glAccount.trim(),
        account_name: accountName.trim() || null,
        effective_from: effectiveFrom,
      });
      toast.success("Mapping saved (prior active terminated).");
      onCreated();
    } catch (e) {
      const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
      toast.error(`Save failed — ${msg}`);
    } finally { setBusy(false); }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm"
         onClick={onClose}>
      <div className="w-full max-w-md rounded-lg border bg-card p-6 shadow-lg"
           onClick={(e) => e.stopPropagation()}>
        <h3 className="mb-3 text-base font-semibold">New GL mapping</h3>
        <p className="mb-3 text-xs text-muted-foreground">
          Saving with an existing mapping_key terminates the prior active
          row at the new effective_from and creates a new active row.
        </p>
        <label className="mb-3 block text-xs">
          <span className="font-medium">Mapping key</span>
          <input type="text" value={mappingKey} onChange={(e) => setMappingKey(e.target.value)}
                 placeholder="e.g. claim_reimbursement / transaction_fee / admin_fee"
                 className="mt-1 w-full rounded-md border bg-background px-3 py-2 font-mono text-sm" />
        </label>
        <label className="mb-3 block text-xs">
          <span className="font-medium">GL account</span>
          <input type="text" value={glAccount} onChange={(e) => setGlAccount(e.target.value)}
                 className="mt-1 w-full rounded-md border bg-background px-3 py-2 font-mono text-sm" />
        </label>
        <label className="mb-3 block text-xs">
          <span className="font-medium">Account name (optional)</span>
          <input type="text" value={accountName} onChange={(e) => setAccountName(e.target.value)}
                 className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm" />
        </label>
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
          <button onClick={handleSave} disabled={busy || !mappingKey.trim() || !glAccount.trim()}
                  className="inline-flex items-center gap-1.5 rounded-md bg-emerald-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-600 disabled:opacity-50">
            {busy && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            Save
          </button>
        </div>
      </div>
    </div>
  );
}
