// Step 2 — Map Fields
// Two-column mapping UI with fuzzy auto-match (fuse.js) and @dnd-kit drag override.
"use client";

import React, { useEffect, useState } from "react";
import { DndContext, closestCenter, DragEndEvent } from "@dnd-kit/core";
import { ArrowRight, ChevronDown, Save } from "lucide-react";
import Fuse from "fuse.js";
import { getMappingTemplates, saveMappingTemplate } from "@shared/lib/billing-api";
import { cn } from "@shared/lib/format";
import { BillingCycleWizardData } from "./types";
import type { MappingTemplate, FieldMapping } from "@shared/types/billing";

// System fields the upload must map to
const SYSTEM_FIELDS = [
  { id: "member_id", label: "Member ID", required: true },
  { id: "pharmacy_npi", label: "Pharmacy NPI", required: true },
  { id: "drug_ndc", label: "Drug NDC (11 digit)", required: true },
  { id: "fill_date", label: "Fill Date", required: true },
  { id: "days_supply", label: "Days Supply", required: true },
  { id: "quantity", label: "Quantity", required: true },
  { id: "ingredient_cost", label: "Ingredient Cost", required: true },
  { id: "dispensing_fee", label: "Dispensing Fee", required: true },
  { id: "copay", label: "Copay", required: true },
  { id: "plan_paid", label: "Plan Paid", required: true },
  { id: "client_id", label: "Client ID", required: false },
  { id: "program_id", label: "Program ID", required: false },
  { id: "prescriber_npi", label: "Prescriber NPI", required: false },
  { id: "diagnosis_code", label: "Diagnosis Code", required: false },
];

interface MapFieldsStepProps {
  data: BillingCycleWizardData;
  onChange: (partial: Partial<BillingCycleWizardData>) => void;
}

function fuzzyAutoMap(sourceColumns: string[]): FieldMapping[] {
  const fuse = new Fuse(SYSTEM_FIELDS, {
    keys: ["id", "label"],
    threshold: 0.4,
  });

  const mappings: FieldMapping[] = [];
  const usedTargets = new Set<string>();

  for (const col of sourceColumns) {
    const results = fuse.search(col);
    if (results.length > 0 && !usedTargets.has(results[0].item.id)) {
      usedTargets.add(results[0].item.id);
      mappings.push({
        source_column: col,
        target_field: results[0].item.id,
        confidence: 1 - (results[0].score ?? 0.5),
      });
    } else {
      mappings.push({
        source_column: col,
        target_field: "",
        confidence: 0,
      });
    }
  }

  return mappings;
}

export function MapFieldsStep({ data, onChange }: MapFieldsStepProps) {
  const [templates, setTemplates] = useState<MappingTemplate[]>([]);
  const [loadingTemplates, setLoadingTemplates] = useState(true);
  const [savingTemplate, setSavingTemplate] = useState(false);
  const [templateName, setTemplateName] = useState("");
  const [showSaveForm, setShowSaveForm] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Initialize mappings from auto-map if not already set
  useEffect(() => {
    if (data.field_mappings.length === 0 && data.detected_columns.length > 0) {
      onChange({ field_mappings: fuzzyAutoMap(data.detected_columns) });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data.detected_columns]);

  // Load mapping templates
  useEffect(() => {
    getMappingTemplates()
      .then(setTemplates)
      .catch(() => {
        // Templates optional — proceed without them
      })
      .finally(() => setLoadingTemplates(false));
  }, []);

  const mappings = data.field_mappings;

  const updateMapping = (sourceColumn: string, targetField: string) => {
    onChange({
      field_mappings: mappings.map((m) =>
        m.source_column === sourceColumn
          ? { ...m, target_field: targetField, confidence: 1 }
          : m
      ),
    });
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    // Swap target fields of two mappings
    const srcA = active.id as string;
    const srcB = over.id as string;
    const mapA = mappings.find((m) => m.source_column === srcA);
    const mapB = mappings.find((m) => m.source_column === srcB);
    if (!mapA || !mapB) return;
    onChange({
      field_mappings: mappings.map((m) => {
        if (m.source_column === srcA) return { ...m, target_field: mapB.target_field };
        if (m.source_column === srcB) return { ...m, target_field: mapA.target_field };
        return m;
      }),
    });
  };

  const handleTemplateSelect = (templateId: string) => {
    const tpl = templates.find((t) => t.id === templateId);
    if (!tpl) return;
    onChange({
      mapping_template_id: templateId,
      field_mappings: tpl.mappings.map((m) => ({ ...m, confidence: 1 })),
    });
  };

  const handleSaveTemplate = async () => {
    if (!templateName.trim() || !data.upload_id) return;
    setSavingTemplate(true);
    setSaveError(null);
    try {
      const saved = await saveMappingTemplate({
        name: templateName.trim(),
        client_id: "current", // TODO: get from context/route
        upload_id: data.upload_id,
        mappings,
      });
      setTemplates((prev) => [saved, ...prev]);
      onChange({ mapping_template_id: saved.id });
      setShowSaveForm(false);
      setTemplateName("");
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Failed to save template");
    } finally {
      setSavingTemplate(false);
    }
  };

  const requiredFields = SYSTEM_FIELDS.filter((f) => f.required);
  const mappedRequired = requiredFields.filter((f) =>
    mappings.some((m) => m.target_field === f.id)
  );

  return (
    <div className="space-y-5">
      {/* Template selector */}
      {!loadingTemplates && templates.length > 0 && (
        <div className="flex items-center gap-3">
          <label className="text-sm font-medium text-slate-300 whitespace-nowrap">
            Load template:
          </label>
          <div className="relative flex-1 max-w-xs">
            <select
              value={data.mapping_template_id ?? ""}
              onChange={(e) => handleTemplateSelect(e.target.value)}
              className="w-full appearance-none pl-3 pr-8 py-2 text-sm rounded-md border border-ifx-border-dark bg-navy-900 text-white focus:outline-none focus:ring-2 focus:ring-teal-500/40"
              aria-label="Load mapping template"
            >
              <option value="">Select a saved template…</option>
              {templates.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
            <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400 pointer-events-none" />
          </div>
        </div>
      )}

      {/* Progress indicator */}
      <div className="flex items-center gap-2 text-sm text-slate-400">
        <span>
          {mappedRequired.length}/{requiredFields.length} required fields mapped
        </span>
        <div className="flex-1 h-1.5 bg-navy-700 rounded-full overflow-hidden">
          <div
            className="h-full bg-teal-500 transition-all"
            style={{
              width: `${
                requiredFields.length > 0
                  ? (mappedRequired.length / requiredFields.length) * 100
                  : 0
              }%`,
            }}
          />
        </div>
      </div>

      {/* Mapping table */}
      <DndContext collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <div className="rounded-lg border border-ifx-border-dark overflow-hidden">
          <div className="grid grid-cols-[1fr_auto_1fr] gap-0 bg-navy-900/80 px-4 py-2 text-xs font-semibold text-slate-400 uppercase tracking-wide border-b border-ifx-border-dark">
            <span>Source Column</span>
            <span />
            <span>System Field</span>
          </div>
          <div className="divide-y divide-ifx-border-dark/50">
            {mappings.map((mapping) => (
              <div
                key={mapping.source_column}
                className="grid grid-cols-[1fr_auto_1fr] items-center gap-3 px-4 py-2.5 hover:bg-navy-700/20 transition-colors"
              >
                <span className="text-sm font-mono text-slate-200 truncate">
                  {mapping.source_column}
                  {mapping.confidence > 0 && mapping.confidence < 1 && (
                    <span className="ml-2 text-xs text-slate-500">
                      ({Math.round(mapping.confidence * 100)}% match)
                    </span>
                  )}
                </span>
                <ArrowRight className="w-4 h-4 text-slate-600 shrink-0" aria-hidden />
                <select
                  value={mapping.target_field}
                  onChange={(e) => updateMapping(mapping.source_column, e.target.value)}
                  className={cn(
                    "w-full pl-2 pr-6 py-1.5 text-sm rounded border bg-navy-900 text-white focus:outline-none focus:ring-1 focus:ring-teal-500/40 appearance-none",
                    mapping.target_field
                      ? "border-teal-500/30 text-slate-200"
                      : "border-ifx-border-dark text-slate-500"
                  )}
                  aria-label={`Map ${mapping.source_column}`}
                >
                  <option value="">— skip —</option>
                  {SYSTEM_FIELDS.map((f) => (
                    <option key={f.id} value={f.id}>
                      {f.label}{f.required ? " *" : ""}
                    </option>
                  ))}
                </select>
              </div>
            ))}
          </div>
        </div>
      </DndContext>

      {/* Save template */}
      <div>
        {!showSaveForm ? (
          <button
            onClick={() => setShowSaveForm(true)}
            className="flex items-center gap-1.5 text-sm text-teal-400 hover:text-teal-300"
          >
            <Save className="w-4 h-4" />
            Save as template for reuse
          </button>
        ) : (
          <div className="flex items-center gap-2 p-3 rounded-lg border border-ifx-border-dark bg-navy-900/40">
            <input
              type="text"
              value={templateName}
              onChange={(e) => setTemplateName(e.target.value)}
              placeholder="Template name (e.g. Acme Standard Format)"
              className="flex-1 px-3 py-1.5 text-sm rounded border border-ifx-border-dark bg-navy-900 text-white placeholder:text-slate-600 focus:outline-none focus:ring-1 focus:ring-teal-500/40"
              onKeyDown={(e) => e.key === "Enter" && handleSaveTemplate()}
            />
            <button
              onClick={handleSaveTemplate}
              disabled={!templateName.trim() || savingTemplate}
              className="px-3 py-1.5 text-sm rounded bg-teal-500 text-white hover:bg-teal-600 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {savingTemplate ? "Saving…" : "Save"}
            </button>
            <button
              onClick={() => setShowSaveForm(false)}
              className="px-3 py-1.5 text-sm rounded border border-ifx-border-dark text-slate-400 hover:text-slate-200"
            >
              Cancel
            </button>
            {saveError && (
              <span className="text-xs text-red-400">{saveError}</span>
            )}
          </div>
        )}
      </div>

      <p className="text-xs text-slate-500">
        * Required fields. Drag rows to swap mappings, or use the dropdowns to override auto-detected assignments.
      </p>
    </div>
  );
}
