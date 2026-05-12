"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Building2, CheckCircle2, Loader2 } from "lucide-react";

import { ApiClientError } from "@shared/lib/api-client";
import {
  getTenantAchOrigination, upsertTenantAchOrigination,
  type TenantAchOrigination, type UpsertTenantAchOriginationRequest,
} from "@shared/lib/paysync-api";

const DEFAULTS: UpsertTenantAchOriginationRequest = {
  immediate_destination: "",
  immediate_origin: "",
  originating_dfi_id: "",
  company_name: "",
  company_identification: "",
  company_entry_description: "PHARM PMT",
  service_class_code: "220",
  file_id_modifier_seed: "A",
  effective_entry_date_offset_days: 1,
  company_descriptive_date: null,
  effective_from: new Date().toISOString().slice(0, 10),
};

export default function TenantAchOriginationPage() {
  const [form, setForm] = useState<UpsertTenantAchOriginationRequest>(DEFAULTS);
  const [existing, setExisting] = useState<TenantAchOrigination | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    getTenantAchOrigination()
      .then((row) => {
        if (row) {
          setExisting(row);
          setForm({
            immediate_destination: row.immediate_destination,
            immediate_origin: row.immediate_origin,
            originating_dfi_id: row.originating_dfi_id,
            company_name: row.company_name,
            company_identification: row.company_identification,
            company_entry_description: row.company_entry_description,
            service_class_code: row.service_class_code,
            file_id_modifier_seed: row.file_id_modifier_seed,
            effective_entry_date_offset_days: row.effective_entry_date_offset_days,
            company_descriptive_date: row.company_descriptive_date,
            effective_from: row.effective_from,
          });
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  function update<K extends keyof UpsertTenantAchOriginationRequest>(k: K, v: UpsertTenantAchOriginationRequest[K]) {
    setForm({ ...form, [k]: v });
  }

  async function handleSubmit() {
    setSubmitting(true);
    try {
      const updated = await upsertTenantAchOrigination(form);
      setExisting(updated);
      toast.success("ACH origination saved.");
    } catch (e) {
      const msg = e instanceof ApiClientError ? `${e.code}: ${e.message}` : String(e);
      toast.error(`Save failed — ${msg}`);
    } finally { setSubmitting(false); }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12 text-muted-foreground">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Loading…
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl p-6">
      <div className="mb-6 flex items-start gap-3">
        <div className="rounded-md bg-violet-500/10 p-2">
          <Building2 className="h-5 w-5 text-violet-500" />
        </div>
        <div>
          <h1 className="text-2xl font-bold">Tenant ACH origination</h1>
          <p className="text-sm text-muted-foreground">
            NACHA originator config for this tenant. Required before any
            payment batch can generate a NACHA file. Validation runs ABA
            checksum + per-field format on save.
          </p>
        </div>
      </div>

      <section className="rounded-lg border bg-card p-4">
        <div className="grid gap-4 md:grid-cols-2">
          <Field label="Immediate destination (10 digits)"
                 hint="ODFI 9-digit RTN with leading space ('1' or '0' prefix per NACHA)">
            <input type="text" value={form.immediate_destination}
                   onChange={(e) => update("immediate_destination", e.target.value)}
                   className="rounded-md border bg-background px-3 py-2 font-mono text-sm" />
          </Field>
          <Field label="Immediate origin (10 digits)"
                 hint="Originator IRS EIN with '1' prefix or 9-digit RTN">
            <input type="text" value={form.immediate_origin}
                   onChange={(e) => update("immediate_origin", e.target.value)}
                   className="rounded-md border bg-background px-3 py-2 font-mono text-sm" />
          </Field>
          <Field label="Originating DFI (8 digits)"
                 hint="ODFI ABA prefix (first 8 digits of immediate destination)">
            <input type="text" value={form.originating_dfi_id}
                   onChange={(e) => update("originating_dfi_id", e.target.value)}
                   className="rounded-md border bg-background px-3 py-2 font-mono text-sm" />
          </Field>
          <Field label="Service class code"
                 hint="200 = mixed, 220 = credits only, 225 = debits only">
            <select value={form.service_class_code}
                    onChange={(e) => update("service_class_code", e.target.value)}
                    className="rounded-md border bg-background px-3 py-2 text-sm">
              <option value="200">200 — mixed</option>
              <option value="220">220 — credits only</option>
              <option value="225">225 — debits only</option>
            </select>
          </Field>
          <Field label="Company name (max 16 chars)">
            <input type="text" value={form.company_name} maxLength={16}
                   onChange={(e) => update("company_name", e.target.value)}
                   className="rounded-md border bg-background px-3 py-2 text-sm" />
          </Field>
          <Field label="Company identification (10 chars)"
                 hint="Typically '1' + 9-digit IRS EIN">
            <input type="text" value={form.company_identification}
                   onChange={(e) => update("company_identification", e.target.value)}
                   className="rounded-md border bg-background px-3 py-2 font-mono text-sm" />
          </Field>
          <Field label="Company entry description (10 chars)">
            <input type="text" value={form.company_entry_description} maxLength={10}
                   onChange={(e) => update("company_entry_description", e.target.value)}
                   className="rounded-md border bg-background px-3 py-2 text-sm" />
          </Field>
          <Field label="File ID modifier seed (A-Z, 0-9)">
            <input type="text" value={form.file_id_modifier_seed} maxLength={1}
                   onChange={(e) => update("file_id_modifier_seed", e.target.value.toUpperCase())}
                   className="rounded-md border bg-background px-3 py-2 font-mono text-sm" />
          </Field>
          <Field label="Effective entry date offset (days)"
                 hint="Days between file creation and ACH effective date">
            <input type="number" value={form.effective_entry_date_offset_days}
                   onChange={(e) => update("effective_entry_date_offset_days", Number(e.target.value))}
                   className="rounded-md border bg-background px-3 py-2 text-sm" />
          </Field>
          <Field label="Company descriptive date (YYMMDD, optional)">
            <input type="text" value={form.company_descriptive_date ?? ""} maxLength={6}
                   onChange={(e) => update("company_descriptive_date", e.target.value || null)}
                   className="rounded-md border bg-background px-3 py-2 font-mono text-sm" />
          </Field>
          <Field label="Effective from">
            <input type="date" value={form.effective_from}
                   onChange={(e) => update("effective_from", e.target.value)}
                   className="rounded-md border bg-background px-3 py-2 text-sm" />
          </Field>
        </div>

        <div className="mt-6 flex items-center justify-between border-t pt-4">
          {existing && (
            <p className="text-xs text-muted-foreground">
              Last saved {new Date(existing.effective_from).toLocaleDateString()}
            </p>
          )}
          <button onClick={handleSubmit} disabled={submitting}
                  className="inline-flex items-center gap-1.5 rounded-md bg-violet-500 px-4 py-2 text-sm font-medium text-white hover:bg-violet-600 disabled:opacity-50">
            {submitting
              ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
              : <CheckCircle2 className="h-3.5 w-3.5" />}
            Save
          </button>
        </div>
      </section>
    </div>
  );
}

function Field({
  label, hint, children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1 text-xs">
      <span className="font-medium">{label}</span>
      {children}
      {hint && <span className="text-[11px] text-muted-foreground">{hint}</span>}
    </label>
  );
}
