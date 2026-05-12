"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Calendar, Loader2, Plus, Trash2 } from "lucide-react";

import { ApiClientError } from "@shared/lib/api-client";
import {
  listCycleSchedules, createCycleSchedule, deleteCycleSchedule,
  type CycleSchedule, type Cadence, type ScheduleScope,
  type CycleType, type CreateCycleScheduleRequest,
} from "@shared/lib/paysync-api";

import { DestructiveActionDialog } from "@/components/paysync/destructive-action-dialog";

const CADENCE_TEMPLATES: Record<Cadence, Record<string, unknown>> = {
  daily: {},
  weekly: { day_of_week: "monday" },
  bi_weekly: { day_of_week: "monday", anchor_date: "2026-01-05" },
  semi_monthly: { close_days: [15, 0] },
  monthly: { close_day: 0 },
};

export default function CycleSchedulesPage() {
  const [rows, setRows] = useState<CycleSchedule[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [deleteId, setDeleteId] = useState<string | null>(null);

  function refresh() {
    setLoading(true);
    listCycleSchedules()
      .then(setRows)
      .catch((e: unknown) => {
        const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
        toast.error(`Failed to load schedules — ${msg}`);
      })
      .finally(() => setLoading(false));
  }
  useEffect(() => { refresh(); }, []);

  async function handleDelete() {
    if (!deleteId) return;
    try {
      await deleteCycleSchedule(deleteId);
      toast.success("Schedule deleted.");
      setDeleteId(null);
      refresh();
    } catch (e) {
      const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
      toast.error(`Delete failed — ${msg}`);
    }
  }

  return (
    <div className="mx-auto max-w-[1400px] p-6">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div className="flex items-start gap-3">
          <div className="rounded-md bg-teal-500/10 p-2">
            <Calendar className="h-5 w-5 text-teal-500" />
          </div>
          <div>
            <h1 className="text-2xl font-bold">Cycle schedules</h1>
            <p className="text-sm text-muted-foreground">
              Cadence + scope rules drive automatic cycle opening.
              Resolution waterfall: pharmacy_state → npi → program →
              client → tenant.
            </p>
          </div>
        </div>
        <button onClick={() => setShowAdd(true)}
                className="inline-flex items-center gap-1.5 rounded-md bg-teal-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-teal-600">
          <Plus className="h-3.5 w-3.5" /> New schedule
        </button>
      </div>

      {loading ? <p className="text-sm text-muted-foreground">Loading…</p>
        : rows.length === 0
        ? <div className="rounded-md border border-dashed p-8 text-center text-sm text-muted-foreground">
            No schedules. Create one to start opening cycles automatically.
          </div>
        : (
          <div className="rounded-lg border bg-card">
            <table className="w-full text-sm">
              <thead className="bg-muted/30 text-xs uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 text-left">Name</th>
                  <th className="px-3 py-2 text-left">Cycle type</th>
                  <th className="px-3 py-2 text-left">Cadence</th>
                  <th className="px-3 py-2 text-left">Scope</th>
                  <th className="px-3 py-2 text-left">Effective</th>
                  <th className="px-3 py-2"></th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {rows.map((s) => (
                  <tr key={s.id}>
                    <td className="px-3 py-1.5 text-sm font-medium">{s.name}</td>
                    <td className="px-3 py-1.5 text-xs">{s.cycle_type}</td>
                    <td className="px-3 py-1.5 text-xs">{s.cadence}</td>
                    <td className="px-3 py-1.5 text-xs">
                      {s.scope_type}
                      {s.scope_value && <span className="ml-1 font-mono text-muted-foreground">{s.scope_value}</span>}
                    </td>
                    <td className="px-3 py-1.5 text-xs">
                      {s.effective_from}
                      {s.termination_date && <span className="text-muted-foreground"> → {s.termination_date}</span>}
                    </td>
                    <td className="px-3 py-1.5 text-right">
                      <button onClick={() => setDeleteId(s.id)}
                              className="rounded-md border border-rose-500/50 p-1 text-rose-600 hover:bg-rose-500/5"
                              aria-label="Delete schedule">
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

      {showAdd && (
        <NewScheduleWizard onClose={() => setShowAdd(false)}
                           onCreated={() => { setShowAdd(false); refresh(); }} />
      )}

      <DestructiveActionDialog
        open={!!deleteId}
        onOpenChange={(o) => !o && setDeleteId(null)}
        title="Delete cycle schedule"
        description="The schedule won't drive new cycle openings. Existing
        cycles created under it remain unchanged."
        actionLabel="Delete"
        onConfirm={handleDelete}
      />
    </div>
  );
}

function NewScheduleWizard({
  onClose, onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [name, setName] = useState("");
  const [cycleType, setCycleType] = useState<CycleType>("payment_cycle");
  const [cadence, setCadence] = useState<Cadence>("semi_monthly");
  const [scopeType, setScopeType] = useState<ScheduleScope>("tenant");
  const [scopeValue, setScopeValue] = useState("");
  const [effectiveFrom, setEffectiveFrom] = useState(new Date().toISOString().slice(0, 10));
  const [cadenceConfigJson, setCadenceConfigJson] = useState(
    JSON.stringify(CADENCE_TEMPLATES.semi_monthly, null, 2),
  );
  const [busy, setBusy] = useState(false);

  function changeCadence(c: Cadence) {
    setCadence(c);
    setCadenceConfigJson(JSON.stringify(CADENCE_TEMPLATES[c], null, 2));
  }

  async function handleCreate() {
    let cadence_config: Record<string, unknown>;
    try {
      cadence_config = JSON.parse(cadenceConfigJson);
    } catch {
      toast.error("Cadence config must be valid JSON.");
      return;
    }
    setBusy(true);
    try {
      const req: CreateCycleScheduleRequest = {
        name: name.trim(),
        cycle_type: cycleType,
        cadence,
        cadence_config,
        scope_type: scopeType,
        scope_value: scopeType === "tenant" ? null : (scopeValue.trim() || null),
        effective_from: effectiveFrom,
      };
      await createCycleSchedule(req);
      toast.success("Schedule created.");
      onCreated();
    } catch (e) {
      const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
      toast.error(`Create failed — ${msg}`);
    } finally { setBusy(false); }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm"
         onClick={onClose}>
      <div className="w-full max-w-lg rounded-lg border bg-card p-6 shadow-lg"
           onClick={(e) => e.stopPropagation()}>
        <h3 className="mb-4 text-base font-semibold">New cycle schedule</h3>

        <label className="mb-3 block text-xs">
          <span className="font-medium">Name</span>
          <input type="text" value={name} onChange={(e) => setName(e.target.value)}
                 placeholder="e.g. Standard Bi-Monthly Payment"
                 className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm" />
        </label>

        <div className="mb-3 grid grid-cols-2 gap-3 text-xs">
          <label>
            <span className="font-medium">Cycle type</span>
            <select value={cycleType} onChange={(e) => setCycleType(e.target.value as CycleType)}
                    className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm">
              <option value="payment_cycle">Payment cycle</option>
              <option value="invoice_cycle">Invoice cycle</option>
            </select>
          </label>
          <label>
            <span className="font-medium">Cadence</span>
            <select value={cadence} onChange={(e) => changeCadence(e.target.value as Cadence)}
                    className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm">
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
              <option value="bi_weekly">Bi-weekly</option>
              <option value="semi_monthly">Semi-monthly (1H/2H)</option>
              <option value="monthly">Monthly</option>
            </select>
          </label>
        </div>

        <label className="mb-3 block text-xs">
          <span className="font-medium">Cadence config (JSON)</span>
          <textarea value={cadenceConfigJson}
                    onChange={(e) => setCadenceConfigJson(e.target.value)}
                    rows={4}
                    className="mt-1 w-full rounded-md border bg-background px-3 py-2 font-mono text-xs" />
        </label>

        <div className="mb-3 grid grid-cols-2 gap-3 text-xs">
          <label>
            <span className="font-medium">Scope type</span>
            <select value={scopeType} onChange={(e) => setScopeType(e.target.value as ScheduleScope)}
                    className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm">
              <option value="tenant">Tenant (default)</option>
              <option value="client">Client</option>
              <option value="program">Program</option>
              <option value="pharmacy_npi">Pharmacy NPI</option>
              <option value="pharmacy_state">Pharmacy state</option>
            </select>
          </label>
          {scopeType !== "tenant" && (
            <label>
              <span className="font-medium">Scope value</span>
              <input type="text" value={scopeValue} onChange={(e) => setScopeValue(e.target.value)}
                     placeholder={scopeType === "pharmacy_npi" ? "NPI" :
                                  scopeType === "pharmacy_state" ? "2-letter code" : "UUID"}
                     className="mt-1 w-full rounded-md border bg-background px-3 py-2 font-mono text-sm" />
            </label>
          )}
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
          <button onClick={handleCreate} disabled={busy || !name.trim()}
                  className="inline-flex items-center gap-1.5 rounded-md bg-teal-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-teal-600 disabled:opacity-50">
            {busy && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            Create
          </button>
        </div>
      </div>
    </div>
  );
}
