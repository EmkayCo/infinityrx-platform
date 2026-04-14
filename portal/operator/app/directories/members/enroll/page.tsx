"use client";

import React, { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { Upload, FileText, CheckCircle, AlertTriangle, XCircle } from "lucide-react";
import { Wizard, useWizard, type WizardStep } from "@shared/components/wizard";
import { API_URLS } from "@shared/lib/constants";
import { apiPost } from "@shared/lib/api-client";
import { cn } from "@shared/lib/format";
import { useRouter } from "next/navigation";

const STEPS: WizardStep[] = [
  { id: "upload", title: "Upload File", description: "834 EDI or CSV" },
  { id: "validate", title: "Validate", description: "Review errors" },
  { id: "preview", title: "Preview", description: "Member changes" },
  { id: "confirm", title: "Confirm", description: "Apply changes" },
];

interface ValidationError {
  row: number;
  field: string;
  message: string;
  original_value: string;
}

interface EnrollmentPreview {
  adds: number;
  updates: number;
  terms: number;
  total_records: number;
  warnings: string[];
}

// ── Step 1: Upload ────────────────────────────────────────────────────────────
function UploadStep({
  onFileSelect,
  file,
}: {
  onFileSelect: (f: File) => void;
  file: File | null;
}) {
  const onDrop = useCallback(
    (accepted: File[]) => {
      if (accepted[0]) onFileSelect(accepted[0]);
    },
    [onFileSelect]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "text/csv": [".csv"],
      "text/plain": [".txt"],
      "application/octet-stream": [".edi", ".x12"],
    },
    maxFiles: 1,
    maxSize: 100 * 1024 * 1024, // 100MB
  });

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-400">
        Upload an 834 EDI file or CSV with member enrollment data.
      </p>
      <div
        {...getRootProps()}
        className={cn(
          "border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors",
          isDragActive
            ? "border-teal-500 bg-teal-900/10"
            : "border-ifx-border-dark hover:border-teal-600/40 hover:bg-navy-700/20"
        )}
      >
        <input {...getInputProps()} />
        <Upload className={cn("w-10 h-10 mx-auto mb-3", isDragActive ? "text-teal-400" : "text-slate-500")} />
        <p className="text-sm text-slate-300 font-medium">
          {isDragActive ? "Drop file here" : "Drag & drop your enrollment file"}
        </p>
        <p className="text-xs text-slate-500 mt-1">
          Supported: .csv, .edi, .x12 · Max 100MB
        </p>
      </div>

      {file && (
        <div className="flex items-center gap-3 p-3 rounded-lg border border-teal-600/30 bg-teal-900/10">
          <FileText className="w-5 h-5 text-teal-400" />
          <div>
            <p className="text-sm font-medium text-white">{file.name}</p>
            <p className="text-xs text-slate-400">
              {(file.size / 1024).toFixed(1)} KB
            </p>
          </div>
          <CheckCircle className="w-4 h-4 text-green-400 ml-auto" />
        </div>
      )}
    </div>
  );
}

// ── Step 2: Validate ──────────────────────────────────────────────────────────
function ValidateStep({
  file,
  onValidated,
}: {
  file: File | null;
  onValidated: (errors: ValidationError[], totalValid: number) => void;
}) {
  const [isValidating, setIsValidating] = React.useState(false);
  const [errors, setErrors] = React.useState<ValidationError[]>([]);
  const [totalValid, setTotalValid] = React.useState(0);
  const [done, setDone] = React.useState(false);

  React.useEffect(() => {
    if (!file || done) return;
    setIsValidating(true);
    apiPost<{ errors: ValidationError[]; total_valid: number; valid: boolean }>(
      `${API_URLS.memberManagement}/api/v1/members/enrollment/validate`,
      { filename: file.name, size: file.size }
    )
      .then((res) => {
        setErrors(res.errors ?? []);
        setTotalValid(res.total_valid ?? (res.valid ? 100 : 0));
        onValidated(res.errors ?? [], res.total_valid ?? (res.valid ? 100 : 0));
        setDone(true);
      })
      .catch(() => { setDone(true); })
      .finally(() => setIsValidating(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [file]);

  return (
    <div className="space-y-4">
      {isValidating && (
        <div className="flex items-center gap-3">
          <div className="w-5 h-5 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm text-slate-300">Validating file...</span>
        </div>
      )}
      {done && (
        <div className="grid grid-cols-3 gap-3">
          <div className="rounded-lg border border-green-700/30 bg-green-900/10 p-3 text-center">
            <CheckCircle className="w-5 h-5 text-green-400 mx-auto mb-1" />
            <p className="text-lg font-bold text-white">{totalValid}</p>
            <p className="text-xs text-slate-400">Valid records</p>
          </div>
          <div className="rounded-lg border border-yellow-700/30 bg-yellow-900/10 p-3 text-center">
            <AlertTriangle className="w-5 h-5 text-yellow-400 mx-auto mb-1" />
            <p className="text-lg font-bold text-white">0</p>
            <p className="text-xs text-slate-400">Warnings</p>
          </div>
          <div className={cn("rounded-lg border p-3 text-center", errors.length > 0 ? "border-red-700/30 bg-red-900/10" : "border-ifx-border-dark bg-navy-900/40")}>
            <XCircle className={cn("w-5 h-5 mx-auto mb-1", errors.length > 0 ? "text-red-400" : "text-slate-500")} />
            <p className="text-lg font-bold text-white">{errors.length}</p>
            <p className="text-xs text-slate-400">Errors</p>
          </div>
        </div>
      )}
      {errors.length > 0 && (
        <div className="rounded-lg border border-red-700/20 overflow-hidden">
          <div className="px-4 py-2.5 bg-red-900/20 border-b border-red-700/20">
            <p className="text-xs font-semibold text-red-300">Validation Errors</p>
          </div>
          <div className="max-h-48 overflow-y-auto divide-y divide-red-900/20">
            {errors.slice(0, 20).map((err, i) => (
              <div key={i} className="px-4 py-2 text-xs">
                <span className="text-slate-400">Row {err.row}</span>
                <span className="text-red-400 mx-1">·</span>
                <span className="text-slate-300">{err.field}:</span>{" "}
                <span className="text-red-300">{err.message}</span>
                {err.original_value && (
                  <span className="text-slate-500"> (got: {err.original_value})</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Step 3: Preview ───────────────────────────────────────────────────────────
function PreviewStep({ file }: { file: File | null }) {
  const [preview, setPreview] = React.useState<EnrollmentPreview | null>(null);

  React.useEffect(() => {
    if (!file) return;
    apiPost<EnrollmentPreview>(
      `${API_URLS.memberManagement}/api/v1/members/enrollment/preview`,
      { filename: file.name, size: file.size }
    )
      .then((res) => setPreview(res))
      .catch(() => {/* no-op */});
  }, [file]);

  return (
    <div className="space-y-4">
      {!preview ? (
        <div className="flex items-center gap-3">
          <div className="w-5 h-5 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm text-slate-300">Loading preview...</span>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-3">
            <div className="rounded-lg border border-green-700/20 bg-green-900/5 p-4 text-center">
              <p className="text-2xl font-bold text-green-400">{preview.adds}</p>
              <p className="text-xs text-slate-400 mt-1">New Members</p>
            </div>
            <div className="rounded-lg border border-blue-700/20 bg-blue-900/5 p-4 text-center">
              <p className="text-2xl font-bold text-blue-400">{preview.updates}</p>
              <p className="text-xs text-slate-400 mt-1">Updates</p>
            </div>
            <div className="rounded-lg border border-red-700/20 bg-red-900/5 p-4 text-center">
              <p className="text-2xl font-bold text-red-400">{preview.terms}</p>
              <p className="text-xs text-slate-400 mt-1">Terminations</p>
            </div>
          </div>
          {preview.warnings.length > 0 && (
            <div className="rounded-lg border border-yellow-700/20 bg-yellow-900/5 p-4">
              <p className="text-xs font-semibold text-yellow-300 mb-2">Warnings</p>
              <ul className="space-y-1">
                {preview.warnings.map((w, i) => (
                  <li key={i} className="text-xs text-yellow-300 flex items-start gap-1.5">
                    <span className="mt-0.5">•</span>{w}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ── Step 4: Confirm ───────────────────────────────────────────────────────────
function ConfirmStep({ file }: { file: File | null }) {
  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-ifx-border-dark bg-navy-900/60 p-5">
        <p className="text-sm text-slate-300">
          File: <span className="text-white font-medium">{file?.name ?? "—"}</span>
        </p>
        <p className="text-xs text-slate-400 mt-1">
          Submitting will apply all changes to the member database. This action cannot be automatically undone.
        </p>
      </div>
      <div className="rounded-lg border border-teal-600/20 bg-teal-900/10 p-4">
        <p className="text-sm text-teal-300">
          Click Submit to process the enrollment file and apply member changes.
        </p>
      </div>
    </div>
  );
}

// ── Main Page ────────────────────────────────────────────────────────────────
export default function EnrollPage() {
  const router = useRouter();
  const { currentStep, setStep, isLastStep } = useWizard(STEPS.length, "enrollment");
  const [file, setFile] = useState<File | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleNext = useCallback(async (): Promise<boolean> => {
    if (currentStep === 0 && !file) return false;
    if (isLastStep && file) {
      setIsSubmitting(true);
      try {
        await apiPost(
          `${API_URLS.memberManagement}/api/v1/members/enrollment/apply`,
          { filename: file.name, size: file.size }
        );
        router.push("/directories/members");
        return true;
      } catch {
        return false;
      } finally {
        setIsSubmitting(false);
      }
    }
    return true;
  }, [currentStep, file, isLastStep, router]);

  const stepContent = [
    <UploadStep key="upload" file={file} onFileSelect={setFile} />,
    <ValidateStep key="validate" file={file} onValidated={() => {}} />,
    <PreviewStep key="preview" file={file} />,
    <ConfirmStep key="confirm" file={file} />,
  ];

  return (
    <div className="p-6 h-full flex flex-col">
      <div className="flex-1 max-w-3xl mx-auto w-full" style={{ minHeight: "550px" }}>
        <Wizard
          steps={STEPS}
          currentStep={currentStep}
          onStepChange={setStep}
          onClose={() => router.push("/directories/members")}
          title="Enrollment File Upload"
          onNext={handleNext}
          isNextDisabled={currentStep === 0 && !file}
          isSubmitting={isSubmitting}
          isLastStep={isLastStep}
          nextLabel={isLastStep ? "Apply Changes" : undefined}
        >
          {stepContent[currentStep]}
        </Wizard>
      </div>
    </div>
  );
}
