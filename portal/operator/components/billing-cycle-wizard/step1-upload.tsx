// Step 1 — Upload Claims File
"use client";

import React, { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, FileText, AlertCircle, CheckCircle2 } from "lucide-react";
import { uploadClaimsFile } from "@shared/lib/billing-api";
import { cn } from "@shared/lib/format";
import { BillingCycleWizardData } from "./types";

const ACCEPTED_EXTENSIONS = [".csv", ".xlsx", ".xls", ".txt"];
const ACCEPTED_MIME = {
  "text/csv": [".csv"],
  "text/plain": [".txt"],
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
  "application/vnd.ms-excel": [".xls"],
};

interface UploadStepProps {
  data: BillingCycleWizardData;
  onChange: (partial: Partial<BillingCycleWizardData>) => void;
}

export function UploadStep({ data, onChange }: UploadStepProps) {
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFile = useCallback(
    async (file: File) => {
      setError(null);
      setIsUploading(true);
      setUploadProgress(0);
      try {
        const result = await uploadClaimsFile(file, setUploadProgress);
        onChange({
          upload_id: result.upload_id,
          upload_filename: result.filename,
          upload_size_bytes: result.size_bytes,
          upload_estimated_rows: result.estimated_row_count,
          detected_columns: result.detected_columns,
          is_duplicate: result.is_duplicate,
        });
      } catch (err) {
        setError(err instanceof Error ? err.message : "Upload failed");
      } finally {
        setIsUploading(false);
      }
    },
    [onChange]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: (accepted) => {
      if (accepted.length > 0) handleFile(accepted[0]);
    },
    accept: ACCEPTED_MIME,
    maxFiles: 1,
    disabled: isUploading,
  });

  const formatBytes = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="space-y-6">
      <div className="space-y-1">
        <p className="text-sm text-slate-400">
          Upload a claims file in CSV, Excel, or pipe-delimited format. Accepts files up to 500 MB.
        </p>
        <p className="text-xs text-slate-500">
          Accepted formats: {ACCEPTED_EXTENSIONS.join(", ")}
        </p>
      </div>

      {/* Drop zone */}
      <div
        {...getRootProps()}
        className={cn(
          "relative flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed p-10 cursor-pointer transition-colors",
          isDragActive
            ? "border-teal-400 bg-teal-500/10"
            : "border-ifx-border-dark hover:border-teal-500/60 hover:bg-navy-700/20",
          isUploading && "pointer-events-none opacity-60"
        )}
      >
        <input {...getInputProps()} aria-label="Upload claims file" />
        <Upload className="w-10 h-10 text-teal-400" aria-hidden />
        <div className="text-center">
          {isDragActive ? (
            <p className="text-teal-400 font-medium">Drop the file here</p>
          ) : (
            <>
              <p className="text-slate-200 font-medium">
                Drag and drop your file here
              </p>
              <p className="text-sm text-slate-500 mt-1">
                or{" "}
                <span className="text-teal-400 underline underline-offset-2">
                  browse to select
                </span>
              </p>
            </>
          )}
        </div>
      </div>

      {/* Upload progress */}
      {isUploading && (
        <div className="space-y-2">
          <div className="flex justify-between text-xs text-slate-400">
            <span>Uploading…</span>
            <span>{uploadProgress}%</span>
          </div>
          <div className="h-2 rounded-full bg-navy-700 overflow-hidden">
            <div
              className="h-full bg-teal-500 transition-all duration-300"
              style={{ width: `${uploadProgress}%` }}
              role="progressbar"
              aria-valuenow={uploadProgress}
              aria-valuemin={0}
              aria-valuemax={100}
            />
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/5 p-3">
          <AlertCircle className="w-4 h-4 text-red-400 mt-0.5 shrink-0" />
          <p className="text-sm text-red-400">{error}</p>
        </div>
      )}

      {/* Uploaded file summary */}
      {data.upload_id && !isUploading && (
        <div className="rounded-lg border border-teal-500/30 bg-teal-500/5 p-4 space-y-3">
          <div className="flex items-start gap-3">
            <CheckCircle2 className="w-5 h-5 text-teal-400 mt-0.5 shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="font-medium text-slate-200 truncate">
                {data.upload_filename}
              </p>
              <p className="text-sm text-slate-400 mt-0.5">
                {data.upload_size_bytes != null && formatBytes(data.upload_size_bytes)}
                {data.upload_estimated_rows != null && (
                  <> · ~{data.upload_estimated_rows.toLocaleString()} estimated rows</>
                )}
              </p>
            </div>
            <button
              onClick={() =>
                onChange({
                  upload_id: null,
                  upload_filename: null,
                  upload_size_bytes: null,
                  upload_estimated_rows: null,
                  detected_columns: [],
                  is_duplicate: false,
                })
              }
              className="text-xs text-slate-500 hover:text-slate-300"
            >
              Remove
            </button>
          </div>

          {data.detected_columns.length > 0 && (
            <div>
              <p className="text-xs font-medium text-slate-400 mb-1.5">
                Detected columns ({data.detected_columns.length})
              </p>
              <div className="flex flex-wrap gap-1.5">
                {data.detected_columns.map((col) => (
                  <span
                    key={col}
                    className="px-2 py-0.5 rounded text-xs bg-navy-700 text-slate-300 font-mono"
                  >
                    {col}
                  </span>
                ))}
              </div>
            </div>
          )}

          {data.is_duplicate && (
            <div className="flex items-center gap-2 rounded border border-yellow-500/30 bg-yellow-500/5 px-3 py-2">
              <AlertCircle className="w-4 h-4 text-yellow-400 shrink-0" />
              <p className="text-sm text-yellow-400">
                This file appears to be a duplicate of a recent upload. Review carefully before proceeding.
              </p>
            </div>
          )}

          {data.detected_columns.length > 0 && (
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4 text-slate-400" />
              <span className="text-xs text-slate-400">
                Column mapping will be configured in the next step.
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
