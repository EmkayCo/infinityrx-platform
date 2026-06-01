"use client";

import React, { useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { Upload, FileText, CheckCircle, AlertCircle, Loader2 } from "lucide-react";
import { API_URLS } from "@shared/lib/constants";
import type { DetectionRunRead } from "@/lib/reclaimrx/anomaly-adapter";

const MAX_SYNC_ROWS = 10_000; // configurable guard — reject larger uploads with 413 hint

async function postDetectionRun(formData: FormData): Promise<DetectionRunRead> {
  const url = `${API_URLS.reclaimrx}/api/v1/reclaimrx/detection-runs`;
  const resp = await fetch(url, {
    method: "POST",
    body: formData,
    // Do NOT set Content-Type — browser sets multipart boundary automatically
  });
  if (!resp.ok) {
    let msg = `Upload failed (HTTP ${resp.status})`;
    try {
      const body = (await resp.json()) as { error?: { message?: string } };
      if (body.error?.message) msg = body.error.message;
    } catch {
      // ignore parse error
    }
    throw new Error(msg);
  }
  return resp.json() as Promise<DetectionRunRead>;
}

export default function UploadPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [runLabel, setRunLabel] = useState("");
  const [sizeWarning, setSizeWarning] = useState<string | null>(null);

  const mutation = useMutation<DetectionRunRead, Error, FormData>({
    mutationFn: postDetectionRun,
    onSuccess: (run) => {
      // Invalidate runs list so it refreshes on next visit
      void queryClient.invalidateQueries({ queryKey: ["detection-runs"] });
      // Redirect to leakage view filtered by this run
      router.push(`/reclaimrx/leakage?run_id=${run.id}`);
    },
  });

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null;
    setSelectedFile(file);
    setSizeWarning(null);
    if (file) {
      // Rough row estimate: assume avg ~200 bytes/row
      const estimatedRows = Math.ceil(file.size / 200);
      if (estimatedRows > MAX_SYNC_ROWS) {
        setSizeWarning(
          `File is large (~${(file.size / 1024 / 1024).toFixed(1)} MB, est. ${estimatedRows.toLocaleString()} rows). ` +
          `Synchronous uploads are limited to ~${MAX_SYNC_ROWS.toLocaleString()} rows. Use the CLI for large files.`
        );
      }
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedFile) return;
    const formData = new FormData();
    formData.append("file", selectedFile);
    if (runLabel.trim()) formData.append("run_label", runLabel.trim());
    mutation.mutate(formData);
  }

  const completedRun = mutation.data;

  return (
    <div className="flex flex-col items-center justify-start p-8 min-h-full bg-ifx-gray-50">
      <div className="w-full max-w-xl space-y-6">
        {/* Header */}
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Upload className="w-5 h-5 text-ifx-blue" />
            <h1 className="text-xl font-bold text-ifx-gray-900">Upload Detection CSV</h1>
          </div>
          <p className="text-sm text-ifx-gray-400">
            Upload a claims CSV to trigger the ReclaimRx detection engine. Results appear in
            the Leakage Monitor immediately after completion.
          </p>
        </div>

        {/* Success panel */}
        {completedRun && (
          <div className="rounded-lg border border-green-200 bg-green-50 p-4 space-y-2">
            <div className="flex items-center gap-2 text-green-700 font-semibold">
              <CheckCircle className="w-4 h-4" />
              Detection complete
            </div>
            <div className="text-sm text-green-700 space-y-1">
              <p>
                <span className="font-medium">Run:</span> {completedRun.run_label ?? completedRun.id.slice(0, 8)}
              </p>
              <p>
                <span className="font-medium">Records processed:</span>{" "}
                {completedRun.record_count.toLocaleString()}
              </p>
              <p>
                <span className="font-medium">Anomalies found:</span>{" "}
                <span className="font-bold text-red-600">{completedRun.anomaly_count.toLocaleString()}</span>
              </p>
              {completedRun.data_quality && Object.keys(completedRun.data_quality).length > 0 && (
                <div>
                  <p className="font-medium mt-1">Data quality:</p>
                  <ul className="list-disc list-inside text-xs">
                    {Object.entries(completedRun.data_quality).map(([k, v]) => (
                      <li key={k}>
                        {k}: {String(v)}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
            <p className="text-xs text-green-600 mt-1">Redirecting to Leakage Monitor…</p>
          </div>
        )}

        {/* Error panel */}
        {mutation.isError && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-4 flex items-start gap-2">
            <AlertCircle className="w-4 h-4 text-red-500 mt-0.5 shrink-0" />
            <div className="text-sm text-red-700">
              <p className="font-semibold">Upload failed</p>
              <p>{mutation.error.message}</p>
            </div>
          </div>
        )}

        {/* Upload form */}
        <form onSubmit={handleSubmit} className="bg-white rounded-xl ifx-card-shadow p-6 space-y-5">
          {/* File picker */}
          <div>
            <label className="block text-sm font-medium text-ifx-gray-700 mb-1.5">
              CSV file <span className="text-red-500">*</span>
            </label>
            <div
              className="border-2 border-dashed border-ifx-gray-200 rounded-lg p-6 text-center cursor-pointer hover:border-ifx-blue transition-colors"
              onClick={() => fileInputRef.current?.click()}
            >
              {selectedFile ? (
                <div className="flex items-center justify-center gap-2 text-ifx-gray-700">
                  <FileText className="w-5 h-5 text-ifx-blue" />
                  <span className="font-medium text-sm">{selectedFile.name}</span>
                  <span className="text-xs text-ifx-gray-400">
                    ({(selectedFile.size / 1024).toFixed(0)} KB)
                  </span>
                </div>
              ) : (
                <div className="text-ifx-gray-400 text-sm">
                  <Upload className="w-8 h-8 mx-auto mb-2 opacity-50" />
                  Click to select a CSV file
                </div>
              )}
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,text/csv"
              onChange={handleFileChange}
              className="hidden"
            />
            {sizeWarning && (
              <p className="text-xs text-amber-600 mt-1">{sizeWarning}</p>
            )}
          </div>

          {/* Run label */}
          <div>
            <label
              htmlFor="run-label"
              className="block text-sm font-medium text-ifx-gray-700 mb-1.5"
            >
              Run label <span className="text-ifx-gray-400 font-normal">(optional)</span>
            </label>
            <input
              id="run-label"
              type="text"
              value={runLabel}
              onChange={(e) => setRunLabel(e.target.value)}
              placeholder="e.g. run label — May 2026 batch"
              className="w-full text-sm border border-ifx-gray-200 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-ifx-blue/30 focus:border-ifx-blue"
            />
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={!selectedFile || mutation.isPending}
            className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-lg text-sm font-semibold bg-ifx-blue text-white disabled:opacity-50 disabled:cursor-not-allowed hover:bg-ifx-blue/90 transition-colors"
          >
            {mutation.isPending ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Running detection…
              </>
            ) : (
              <>
                <Upload className="w-4 h-4" />
                Run Detection
              </>
            )}
          </button>
        </form>

        <p className="text-xs text-ifx-gray-400 text-center">
          Large files (&gt;{MAX_SYNC_ROWS.toLocaleString()} rows) should be processed via the CLI:{" "}
          <code className="font-mono bg-ifx-gray-100 px-1 rounded">
            python -m src.cli.detect --file &lt;path&gt;
          </code>
        </p>
      </div>
    </div>
  );
}
