"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { PlusCircle, Trash2 } from "lucide-react";
import { DetailPageLayout } from "@/components/ui/detail-page-layout";
import { apiPost } from "@shared/lib/api-client";

interface DrugEntry { ndc: string; name: string }

interface ProgramFormState {
  name: string;
  manufacturer: string;
  status: "active" | "paused";
  bin: string;
  pcn: string;
  group_code: string;
  budget_annual: string;
  max_benefit_per_patient: string;
  max_fills_per_patient: number;
  effective_date: string;
  term_date: string;
  drugs: DrugEntry[];
}

const EMPTY_FORM: ProgramFormState = {
  name: "",
  manufacturer: "",
  status: "active",
  bin: "",
  pcn: "",
  group_code: "",
  budget_annual: "",
  max_benefit_per_patient: "",
  max_fills_per_patient: 12,
  effective_date: "2026-01-01",
  term_date: "2026-12-31",
  drugs: [{ ndc: "", name: "" }],
};

export default function ProgramConfigPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<ProgramFormState>(EMPTY_FORM);
  const [saved, setSaved] = useState(false);

  const mutation = useMutation({
    mutationFn: (data: ProgramFormState) => apiPost("/api/v1/programs", data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["programs"] });
      setSaved(true);
      setTimeout(() => router.push("/programs"), 1500);
    },
  });

  function setField<K extends keyof ProgramFormState>(key: K, value: ProgramFormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function updateDrug(idx: number, field: keyof DrugEntry, value: string) {
    setForm((prev) => {
      const drugs = [...prev.drugs];
      drugs[idx] = { ...drugs[idx], [field]: value };
      return { ...prev, drugs };
    });
  }

  function addDrug() {
    setForm((prev) => ({ ...prev, drugs: [...prev.drugs, { ndc: "", name: "" }] }));
  }

  function removeDrug(idx: number) {
    setForm((prev) => ({ ...prev, drugs: prev.drugs.filter((_, i) => i !== idx) }));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    mutation.mutate(form);
  }

  return (
    <DetailPageLayout
      backLink={{ href: "/programs", label: "Back to Programs" }}
      title="Program Configuration"
      subtitle="Create or modify a manufacturer copay assistance program. No developer required."
    >
      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Basic Info */}
        <div className="rounded-lg bg-white ifx-card-shadow p-4">
          <h3 className="text-sm font-bold text-ifx-gray-900 mb-4">Basic Information</h3>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="flex flex-col gap-1">
              <label className="text-[10px] font-semibold uppercase tracking-wider text-ifx-gray-400">
                Program Name *
              </label>
              <input
                type="text"
                required
                value={form.name}
                onChange={(e) => setField("name", e.target.value)}
                placeholder="e.g. CardioGuard Copay Program"
                className="rounded border border-ifx-gray-100 px-3 py-2 text-sm text-ifx-gray-900 focus:border-ifx-blue focus:outline-none"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[10px] font-semibold uppercase tracking-wider text-ifx-gray-400">
                Manufacturer *
              </label>
              <input
                type="text"
                required
                value={form.manufacturer}
                onChange={(e) => setField("manufacturer", e.target.value)}
                placeholder="e.g. Helix Biopharma"
                className="rounded border border-ifx-gray-100 px-3 py-2 text-sm text-ifx-gray-900 focus:border-ifx-blue focus:outline-none"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[10px] font-semibold uppercase tracking-wider text-ifx-gray-400">
                Status
              </label>
              <select
                value={form.status}
                onChange={(e) => setField("status", e.target.value as "active" | "paused")}
                className="rounded border border-ifx-gray-100 px-3 py-2 text-sm text-ifx-gray-900 focus:border-ifx-blue focus:outline-none"
              >
                <option value="active">Active</option>
                <option value="paused">Paused</option>
              </select>
            </div>
          </div>
        </div>

        {/* Copay Card Settings */}
        <div className="rounded-lg bg-white ifx-card-shadow p-4">
          <h3 className="text-sm font-bold text-ifx-gray-900 mb-4">Copay Card Settings</h3>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            {(["bin", "pcn", "group_code"] as const).map((field) => (
              <div key={field} className="flex flex-col gap-1">
                <label className="text-[10px] font-semibold uppercase tracking-wider text-ifx-gray-400">
                  {field === "bin" ? "BIN *" : field === "pcn" ? "PCN *" : "Group Code *"}
                </label>
                <input
                  type="text"
                  required
                  value={form[field]}
                  onChange={(e) => setField(field, e.target.value)}
                  className="rounded border border-ifx-gray-100 px-3 py-2 text-sm font-mono text-ifx-gray-900 focus:border-ifx-blue focus:outline-none"
                />
              </div>
            ))}
          </div>
        </div>

        {/* Financial Configuration */}
        <div className="rounded-lg bg-white ifx-card-shadow p-4">
          <h3 className="text-sm font-bold text-ifx-gray-900 mb-4">Financial Configuration</h3>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="flex flex-col gap-1">
              <label className="text-[10px] font-semibold uppercase tracking-wider text-ifx-gray-400">
                Annual Budget ($) *
              </label>
              <input
                type="text"
                required
                pattern="^\d+(\.\d{1,2})?$"
                value={form.budget_annual}
                onChange={(e) => setField("budget_annual", e.target.value)}
                placeholder="5000000.00"
                className="rounded border border-ifx-gray-100 px-3 py-2 text-sm text-ifx-gray-900 focus:border-ifx-blue focus:outline-none"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[10px] font-semibold uppercase tracking-wider text-ifx-gray-400">
                Max Benefit / Patient ($)
              </label>
              <input
                type="text"
                pattern="^\d+(\.\d{1,2})?$"
                value={form.max_benefit_per_patient}
                onChange={(e) => setField("max_benefit_per_patient", e.target.value)}
                placeholder="6000.00"
                className="rounded border border-ifx-gray-100 px-3 py-2 text-sm text-ifx-gray-900 focus:border-ifx-blue focus:outline-none"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[10px] font-semibold uppercase tracking-wider text-ifx-gray-400">
                Max Fills / Patient
              </label>
              <input
                type="number"
                min={1}
                max={36}
                value={form.max_fills_per_patient}
                onChange={(e) => setField("max_fills_per_patient", parseInt(e.target.value, 10))}
                className="rounded border border-ifx-gray-100 px-3 py-2 text-sm text-ifx-gray-900 focus:border-ifx-blue focus:outline-none"
              />
            </div>
          </div>

          <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="flex flex-col gap-1">
              <label className="text-[10px] font-semibold uppercase tracking-wider text-ifx-gray-400">
                Effective Date *
              </label>
              <input
                type="date"
                required
                value={form.effective_date}
                onChange={(e) => setField("effective_date", e.target.value)}
                className="rounded border border-ifx-gray-100 px-3 py-2 text-sm text-ifx-gray-900 focus:border-ifx-blue focus:outline-none"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[10px] font-semibold uppercase tracking-wider text-ifx-gray-400">
                Term Date
              </label>
              <input
                type="date"
                value={form.term_date}
                onChange={(e) => setField("term_date", e.target.value)}
                className="rounded border border-ifx-gray-100 px-3 py-2 text-sm text-ifx-gray-900 focus:border-ifx-blue focus:outline-none"
              />
            </div>
          </div>
        </div>

        {/* Covered Drugs (NDCs) */}
        <div className="rounded-lg bg-white ifx-card-shadow p-4">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-sm font-bold text-ifx-gray-900">Covered Drugs (NDCs)</h3>
            <button
              type="button"
              onClick={addDrug}
              className="inline-flex items-center gap-1.5 text-xs font-medium text-ifx-blue hover:text-ifx-navy"
            >
              <PlusCircle className="h-3.5 w-3.5" /> Add NDC
            </button>
          </div>
          <div className="space-y-2">
            {form.drugs.map((drug, idx) => (
              <div key={idx} className="flex items-center gap-2">
                <input
                  type="text"
                  placeholder="NDC (11 digits)"
                  value={drug.ndc}
                  onChange={(e) => updateDrug(idx, "ndc", e.target.value)}
                  className="w-36 rounded border border-ifx-gray-100 px-2 py-1.5 text-sm font-mono text-ifx-gray-900 focus:border-ifx-blue focus:outline-none"
                />
                <input
                  type="text"
                  placeholder="Drug name"
                  value={drug.name}
                  onChange={(e) => updateDrug(idx, "name", e.target.value)}
                  className="flex-1 rounded border border-ifx-gray-100 px-2 py-1.5 text-sm text-ifx-gray-900 focus:border-ifx-blue focus:outline-none"
                />
                {form.drugs.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeDrug(idx)}
                    className="text-ifx-gray-400 hover:text-red-500 transition-colors"
                    aria-label="Remove drug"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Submit */}
        <div className="flex items-center gap-3">
          <button
            type="submit"
            disabled={mutation.isPending}
            className="rounded-md bg-[var(--ifx-navy)] px-6 py-2 text-sm font-semibold text-white hover:bg-[var(--ifx-navy-dark)] disabled:opacity-50 transition-colors"
          >
            {mutation.isPending ? "Creating…" : "Create Program"}
          </button>
          <button
            type="button"
            onClick={() => router.push("/programs")}
            className="rounded-md border border-ifx-gray-100 px-6 py-2 text-sm font-medium text-ifx-gray-700 hover:border-ifx-blue hover:text-ifx-blue transition-colors"
          >
            Cancel
          </button>
          {saved && (
            <span className="text-sm text-green-600">Program created! Redirecting…</span>
          )}
          {mutation.isError && (
            <span className="text-sm text-red-500">Failed to create — please try again.</span>
          )}
        </div>
      </form>
    </DetailPageLayout>
  );
}
