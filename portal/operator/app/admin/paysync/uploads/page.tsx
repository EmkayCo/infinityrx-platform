"use client";
/**
 * /admin/paysync/uploads -- Paysync uploads list + two-step upload wizard.
 *
 * Step 1: User picks a file via UploadDropzone.
 * Step 2: ColumnMappingStep reads the first 8KB (header only -- no full-file
 *         load) to detect column names, auto-matches to the 8 required billing
 *         fields, lets the user correct any mismatches, then confirms.
 * Step 3: File is POSTed to the BFF with X-Column-Mapping header containing
 *         the confirmed {canonical -> userColumn} JSON. The BFF forwards this
 *         header to billing, which renames columns before CSV validation.
 *         The file body is streamed BFF->billing unchanged (no 100MB buffering).
 *
 * Non-standard column name example:
 *   "Drug Code" -> ndc, "Provider NPI" -> npi, "Billed Amount" -> amount_billed
 *   These would previously 422; now they validate correctly.
 */
import { useState, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  UploadsListPage,
  UploadDropzone,
  ColumnMappingStep,
  type DedupBanner,
} from "@infinityrx/module-paysync";
import type { Upload } from "@infinityrx/contract";

interface UploadListResponse {
  readonly results: Upload[];
  readonly total: number;
  readonly next_cursor?: string;
}

interface ConflictResponse {
  readonly conflict: true;
  readonly existing_upload_id: string;
}

async function fetchUploads(): Promise<UploadListResponse> {
  const res = await fetch("/api/paysync/uploads", { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch uploads");
  return res.json() as Promise<UploadListResponse>;
}

interface PostUploadArgs {
  readonly file: File;
  /** {canonical_field -> user_column_name}. Omit if headers already match. */
  readonly columnMapping?: Record<string, string>;
}

async function postUpload({ file, columnMapping }: PostUploadArgs): Promise<Upload | ConflictResponse> {
  const fd = new FormData();
  fd.append("file", file);

  const headers: Record<string, string> = {};
  if (columnMapping && Object.keys(columnMapping).length > 0) {
    headers["x-column-mapping"] = JSON.stringify(columnMapping);
  }

  const res = await fetch("/api/paysync/uploads", {
    method: "POST",
    headers,
    body: fd,
  });
  const body = await res.json() as Upload | ConflictResponse;
  // 409 is a resolved value (dedup banner), not an error.
  if (res.status === 409) return body;
  if (!res.ok) throw new Error("Upload failed");
  return body;
}

/** Upload flow state machine. */
type UploadPhase =
  | { kind: "idle" }
  | { kind: "mapping"; file: File }
  | { kind: "uploading" }
  | { kind: "done" };

export default function UploadsPage() {
  const queryClient = useQueryClient();
  const [phase, setPhase] = useState<UploadPhase>({ kind: "idle" });
  const [dedupBanner, setDedupBanner] = useState<DedupBanner | undefined>();
  const [uploadError, setUploadError] = useState<string | null>(null);

  const { data, isLoading, error } = useQuery<UploadListResponse, Error>({
    queryKey: ["paysync", "uploads"],
    queryFn: fetchUploads,
    staleTime: 15_000,
  });

  const mutation = useMutation({
    mutationFn: postUpload,
    onSuccess: (result, args) => {
      setPhase({ kind: "idle" });
      if ((result as ConflictResponse).conflict) {
        setDedupBanner({
          existingUploadId: (result as ConflictResponse).existing_upload_id,
          filename: args.file.name,
        });
      } else {
        setDedupBanner(undefined);
        void queryClient.invalidateQueries({ queryKey: ["paysync", "uploads"] });
      }
      setUploadError(null);
    },
    onError: () => {
      setPhase({ kind: "idle" });
      setUploadError("Upload failed. Please check the file and try again.");
    },
  });

  // Step 1: file picked -> enter mapping step.
  const handleFilePicked = useCallback((file: File) => {
    setUploadError(null);
    setDedupBanner(undefined);
    setPhase({ kind: "mapping", file });
  }, []);

  // Step 2: mapping confirmed -> submit.
  const handleMappingConfirm = useCallback((mapping: Record<string, string>, file: File) => {
    setPhase({ kind: "uploading" });
    mutation.mutate({ file, columnMapping: mapping });
  }, [mutation]);

  // Cancel mapping -> back to idle.
  const handleMappingCancel = useCallback(() => {
    setPhase({ kind: "idle" });
  }, []);

  const isUploading = phase.kind === "uploading" || mutation.isPending;

  return (
    <div className="space-y-6 p-6">
      {/* Step 1: always show dropzone unless in mapping step */}
      {phase.kind !== "mapping" && (
        <UploadDropzone
          onUpload={(file) => mutation.mutate({ file })}
          onFilePicked={handleFilePicked}
          disabled={isUploading}
          disabledReason={isUploading ? "Uploading..." : undefined}
          dupUploadId={dedupBanner?.existingUploadId}
          progress={isUploading ? undefined : undefined}
        />
      )}

      {/* Step 2: column mapping */}
      {phase.kind === "mapping" && (
        <div
          data-testid="mapping-step-container"
          style={{
            border: "1px solid #e0e0e0",
            borderRadius: "8px",
            padding: "1.5rem",
            background: "#fafafa",
          }}
        >
          <ColumnMappingStep
            file={phase.file}
            onConfirm={(mapping) => handleMappingConfirm(mapping, phase.file)}
            onCancel={handleMappingCancel}
          />
        </div>
      )}

      {uploadError && (
        <p className="text-sm text-red-600" role="alert">{uploadError}</p>
      )}

      <UploadsListPage
        uploads={data?.results ?? []}
        isLoading={isLoading}
        error={error?.message ?? null}
        dedupBanner={dedupBanner}
      />
    </div>
  );
}
