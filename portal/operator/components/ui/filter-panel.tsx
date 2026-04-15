"use client";

import { useState } from "react";
import { ChevronLeft, ChevronRight, X } from "lucide-react";
import { cn } from "@shared/lib/format";

export type FilterType = "text" | "select" | "multi-select" | "date-range" | "date";

export interface FilterField {
  id: string;
  label: string;
  type: FilterType;
  options?: { value: string; label: string }[];
  placeholder?: string;
}

export type FilterValues = Record<string, unknown>;

export interface SavedPreset {
  name: string;
  values: FilterValues;
}

export type PeriodOption = "monthly" | "weekly" | "daily" | "invoice-cycle";

export interface FilterPanelProps {
  filters: FilterField[];
  values: FilterValues;
  onChange: (values: FilterValues) => void;
  onClear?: () => void;
  onSave?: (name: string) => void;
  savedPresets?: SavedPreset[];
  onApplyPreset?: (preset: SavedPreset) => void;
  collapsible?: boolean;
  periodToggle?: boolean;
  period?: PeriodOption;
  onPeriodChange?: (period: PeriodOption) => void;
  className?: string;
}

const PERIOD_OPTIONS: { id: PeriodOption; label: string }[] = [
  { id: "monthly", label: "Monthly" },
  { id: "weekly", label: "Weekly" },
  { id: "daily", label: "Daily" },
  { id: "invoice-cycle", label: "Invoice Cycle" },
];

export function FilterPanel({
  filters,
  values,
  onChange,
  onClear,
  onSave,
  savedPresets = [],
  onApplyPreset,
  collapsible = true,
  periodToggle = false,
  period = "monthly",
  onPeriodChange,
  className,
}: FilterPanelProps) {
  const [collapsed, setCollapsed] = useState(false);

  if (collapsed) {
    return (
      <button
        type="button"
        onClick={() => setCollapsed(false)}
        className={cn(
          "flex w-10 flex-col items-center gap-2 rounded-lg border border-ifx-gray-100 bg-white py-3 shrink-0 ifx-card-shadow hover:bg-ifx-gray-50",
          className,
        )}
        aria-label="Expand filter panel"
      >
        <ChevronRight className="h-4 w-4 text-ifx-gray-400" />
        <span className="vertical-rl text-[11px] uppercase tracking-wider text-ifx-gray-400">
          Filters
        </span>
      </button>
    );
  }

  const update = (id: string, value: unknown) => {
    onChange({ ...values, [id]: value });
  };

  return (
    <aside
      className={cn(
        "flex w-[280px] flex-col rounded-lg border border-ifx-gray-100 bg-white ifx-card-shadow overflow-hidden shrink-0",
        className,
      )}
      aria-label="Filters"
    >
      <header className="flex items-center justify-between border-b border-ifx-gray-100 px-4 py-3">
        <h3 className="text-sm font-bold text-ifx-gray-900">Filters</h3>
        {collapsible && (
          <button
            type="button"
            onClick={() => setCollapsed(true)}
            className="rounded p-1 text-ifx-gray-400 hover:bg-ifx-gray-50 hover:text-ifx-gray-700"
            aria-label="Collapse filter panel"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
        )}
      </header>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {periodToggle && (
          <div>
            <label className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-ifx-gray-400">
              Period
            </label>
            <div className="inline-flex rounded-md border border-ifx-gray-100 bg-ifx-gray-50 p-0.5">
              {PERIOD_OPTIONS.map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  onClick={() => onPeriodChange?.(opt.id)}
                  className={cn(
                    "rounded px-2 py-1 text-[11px] font-medium transition-colors",
                    period === opt.id
                      ? "bg-white text-ifx-navy shadow-sm"
                      : "text-ifx-gray-400 hover:text-ifx-gray-700",
                  )}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {savedPresets.length > 0 && (
          <div>
            <label className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-ifx-gray-400">
              Saved views
            </label>
            <div className="flex flex-wrap gap-1.5">
              {savedPresets.map((preset) => (
                <button
                  key={preset.name}
                  type="button"
                  onClick={() => onApplyPreset?.(preset)}
                  className="rounded-full border border-ifx-gray-100 bg-white px-2.5 py-1 text-xs text-ifx-gray-700 hover:bg-ifx-lavender hover:border-ifx-blue"
                >
                  {preset.name}
                </button>
              ))}
            </div>
          </div>
        )}

        {filters.map((filter) => (
          <FilterField
            key={filter.id}
            field={filter}
            value={values[filter.id]}
            onChange={(v) => update(filter.id, v)}
          />
        ))}
      </div>

      <footer className="border-t border-ifx-gray-100 p-3 space-y-2">
        {onClear && (
          <button
            type="button"
            onClick={onClear}
            className="inline-flex w-full items-center justify-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium text-ifx-blue hover:bg-ifx-blue/10"
          >
            <X className="h-3.5 w-3.5" />
            Clear all filters
          </button>
        )}
        {onSave && (
          <button
            type="button"
            onClick={() => {
              const name = window.prompt("Save this view as:");
              if (name) onSave(name);
            }}
            className="w-full rounded-md border border-ifx-gray-100 bg-white px-3 py-1.5 text-sm font-medium text-ifx-gray-700 hover:bg-ifx-gray-50"
          >
            Save this view
          </button>
        )}
      </footer>
    </aside>
  );
}

function FilterField({
  field,
  value,
  onChange,
}: {
  field: FilterField;
  value: unknown;
  onChange: (v: unknown) => void;
}) {
  const baseInputClass =
    "w-full rounded-md border border-ifx-gray-100 bg-white px-2.5 py-1.5 text-sm text-ifx-gray-900 focus:outline-none focus:ring-2 focus:ring-ifx-blue/40 focus:border-ifx-blue";

  return (
    <div>
      <label
        htmlFor={`filter-${field.id}`}
        className="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-ifx-gray-400"
      >
        {field.label}
      </label>
      {field.type === "text" && (
        <input
          id={`filter-${field.id}`}
          type="text"
          value={(value as string) ?? ""}
          onChange={(e) => onChange(e.target.value)}
          placeholder={field.placeholder}
          className={baseInputClass}
        />
      )}
      {field.type === "select" && (
        <select
          id={`filter-${field.id}`}
          value={(value as string) ?? ""}
          onChange={(e) => onChange(e.target.value)}
          className={baseInputClass}
        >
          <option value="">All</option>
          {field.options?.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      )}
      {field.type === "multi-select" && (
        <select
          id={`filter-${field.id}`}
          multiple
          value={Array.isArray(value) ? (value as string[]) : []}
          onChange={(e) =>
            onChange(
              Array.from(e.target.selectedOptions).map((opt) => opt.value),
            )
          }
          className={cn(baseInputClass, "h-24")}
        >
          {field.options?.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      )}
      {field.type === "date" && (
        <input
          id={`filter-${field.id}`}
          type="date"
          value={(value as string) ?? ""}
          onChange={(e) => onChange(e.target.value)}
          className={baseInputClass}
        />
      )}
      {field.type === "date-range" && (
        <div className="flex items-center gap-1">
          <input
            type="date"
            value={(value as { from?: string })?.from ?? ""}
            onChange={(e) =>
              onChange({
                ...(typeof value === "object" && value !== null ? value : {}),
                from: e.target.value,
              })
            }
            className={baseInputClass}
            aria-label={`${field.label} from`}
          />
          <span className="text-xs text-ifx-gray-400">to</span>
          <input
            type="date"
            value={(value as { to?: string })?.to ?? ""}
            onChange={(e) =>
              onChange({
                ...(typeof value === "object" && value !== null ? value : {}),
                to: e.target.value,
              })
            }
            className={baseInputClass}
            aria-label={`${field.label} to`}
          />
        </div>
      )}
    </div>
  );
}
