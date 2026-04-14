// Step 3 — Validate
"use client";

import React, { useEffect, useState } from "react";
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  Download,
  RefreshCw,
} from "lucide-react";
import { validateUpload, downloadErrorCsv } from "@shared/lib/billing-api";
import { DataTable, type ColDef } from "@shared/components/data-table";
import { cn } from "@shared/lib/format";
import { BillingCycleWizardData } from "./types";
import type { ValidationError } from "@shared/types/billing";

interface ValidateStepProps {
  data: BillingCycleWizardData;
  onChange: (partial: Partial<BillingCycleWizardData>) => void;
}

const errorColumns: ColDef<ValidationError>[] = [
  { accessorKey: "row", header: "Row", size: 80 },
  { accessorKey: "field", header: "Field", size: 140 },
  {
    accessorKey: "error_message",
    header: "Error",
    cell: ({ row }) => (
      <span className="text-red-400 text-xs">{row.original.error_message}</span>
    ),
  },
  {
    accessorKey: "original_value",
    header: "Original Value",
    cell: ({ row }) => (
      <span className="font-mono text-xs text-slate-400">{row.original.original_value}</span>
    ),
  },
];

export function ValidateStep({ data, onChange }: ValidateStepProps) {
  const [validating, setValidating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runValidation = async () => {
    if (!data.upload_id) return;
    setValidating(true);
    setError(null);
    try {
      const result = await validateUpload(data.upload_id, data.field_mappings);
      onChange({ validation_result: result });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Validation failed");
    } finally {
      setValidating(false);
    }
  };

  // Auto-validate on mount if not already done
  useEffect(() => {
    if (!data.validation_result && data.upload_id) {
      runValidation();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleDownloadErrors = async () => {
    if (!data.upload_id) return;
    const blob = await downloadErrorCsv(data.upload_id);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "validation_errors.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  const result = data.validation_result;

  return (
    <div className="space-y-5">
      {/* Running state */}
      {validating && (
        <div className="space-y-3">
          <div className="flex items-center gap-3 text-slate-400">
            <RefreshCw className="w-5 h-5 animate-spin text-teal-400" />
            <span className="text-sm">Validating records…</span>
          </div>
          <div className="h-2 rounded-full bg-navy-700 overflow-hidden">
            <div className="h-full bg-teal-500 animate-pulse w-1/2 rounded-full" />
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/5 p-3">
          <XCircle className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
          <div>
            <p className="text-sm text-red-400">{error}</p>
            <button
              onClick={runValidation}
              className="text-xs text-teal-400 mt-1 hover:underline"
            >
              Retry validation
            </button>
          </div>
        </div>
      )}

      {/* Results summary */}
      {result && !validating && (
        <div className="space-y-5">
          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-lg border border-teal-500/30 bg-teal-500/5 p-4 text-center">
              <CheckCircle2 className="w-6 h-6 text-teal-400 mx-auto mb-1" />
              <p className="text-2xl font-bold text-teal-400 tabular-nums">
                {result.valid_count.toLocaleString()}
              </p>
              <p className="text-xs text-slate-400 mt-0.5">Valid</p>
            </div>
            <div
              className={cn(
                "rounded-lg border p-4 text-center",
                result.warning_count > 0
                  ? "border-yellow-500/30 bg-yellow-500/5"
                  : "border-ifx-border-dark bg-navy-700/20"
              )}
            >
              <AlertTriangle
                className={cn(
                  "w-6 h-6 mx-auto mb-1",
                  result.warning_count > 0 ? "text-yellow-400" : "text-slate-600"
                )}
              />
              <p
                className={cn(
                  "text-2xl font-bold tabular-nums",
                  result.warning_count > 0 ? "text-yellow-400" : "text-slate-500"
                )}
              >
                {result.warning_count.toLocaleString()}
              </p>
              <p className="text-xs text-slate-400 mt-0.5">Warnings</p>
            </div>
            <div
              className={cn(
                "rounded-lg border p-4 text-center",
                result.error_count > 0
                  ? "border-red-500/30 bg-red-500/5"
                  : "border-ifx-border-dark bg-navy-700/20"
              )}
            >
              <XCircle
                className={cn(
                  "w-6 h-6 mx-auto mb-1",
                  result.error_count > 0 ? "text-red-400" : "text-slate-600"
                )}
              />
              <p
                className={cn(
                  "text-2xl font-bold tabular-nums",
                  result.error_count > 0 ? "text-red-400" : "text-slate-500"
                )}
              >
                {result.error_count.toLocaleString()}
              </p>
              <p className="text-xs text-slate-400 mt-0.5">Errors</p>
            </div>
          </div>

          {/* Options when there are errors */}
          {result.error_count > 0 && (
            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={data.proceed_with_valid_only}
                    onChange={(e) =>
                      onChange({ proceed_with_valid_only: e.target.checked })
                    }
                    className="rounded border-ifx-border-dark bg-navy-900 text-teal-500 focus:ring-teal-500/40"
                  />
                  <span className="text-sm text-slate-300">
                    Proceed with {result.valid_count.toLocaleString()} valid records only
                  </span>
                </label>
              </div>

              <button
                onClick={handleDownloadErrors}
                className="flex items-center gap-2 text-sm text-teal-400 hover:text-teal-300"
              >
                <Download className="w-4 h-4" />
                Download error records as CSV for offline correction
              </button>
            </div>
          )}

          {/* Error detail table */}
          {result.errors.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-slate-300 mb-2">
                Error details ({result.errors.length} shown)
              </h4>
              <DataTable
                columns={errorColumns}
                data={result.errors.slice(0, 100)}
                emptyTitle="No errors"
              />
              {result.errors.length > 100 && (
                <p className="text-xs text-slate-500 mt-2">
                  Showing first 100 of {result.errors.length} errors. Download CSV for full list.
                </p>
              )}
            </div>
          )}

          {/* Re-validate button */}
          <button
            onClick={runValidation}
            className="flex items-center gap-2 text-sm text-slate-400 hover:text-slate-200"
          >
            <RefreshCw className="w-4 h-4" />
            Fix errors and re-validate
          </button>
        </div>
      )}
    </div>
  );
}
