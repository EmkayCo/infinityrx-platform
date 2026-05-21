"use client";
/**
 * /admin/paysync/uploads -- Paysync uploads list + dropzone.
 * Fetches via TanStack Query from /api/paysync/uploads (BFF).
 * Renders UploadsListPage (read list) + UploadDropzone (write path).
 * Mirrors portal/operator/app/admin/paysync/setup/page.tsx pattern.
 */
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  UploadsListPage,
  UploadDropzone,
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

async function postUpload(file: File): Promise<Upload | ConflictResponse> {
  const fd = new FormData();
  fd.append("file", file);
  const res = await fetch("/api/paysync/uploads", { method: "POST", body: fd });
  const body = await res.json() as Upload | ConflictResponse;
  // Propagate 409 as a resolved value so the UI can render the dedup banner.
  if (res.status === 409) return body;
  if (!res.ok) throw new Error("Upload failed");
  return body;
}

export default function UploadsPage() {
  const queryClient = useQueryClient();
  const [dedupBanner, setDedupBanner] = useState<DedupBanner | undefined>();
  const [uploadError, setUploadError] = useState<string | null>(null);

  const { data, isLoading, error } = useQuery<UploadListResponse, Error>({
    queryKey: ["paysync", "uploads"],
    queryFn: fetchUploads,
    staleTime: 15_000,
  });

  const mutation = useMutation({
    mutationFn: postUpload,
    onSuccess: (result, file) => {
      if ((result as ConflictResponse).conflict) {
        setDedupBanner({
          existingUploadId: (result as ConflictResponse).existing_upload_id,
          filename: file.name,
        });
      } else {
        setDedupBanner(undefined);
        void queryClient.invalidateQueries({ queryKey: ["paysync", "uploads"] });
      }
      setUploadError(null);
    },
    onError: () => {
      setUploadError("Upload failed. Please try again.");
    },
  });

  return (
    <div className="space-y-6 p-6">
      <UploadDropzone
        onUpload={(file) => mutation.mutate(file)}
        disabled={mutation.isPending}
        disabledReason={mutation.isPending ? "Uploading..." : undefined}
        dupUploadId={dedupBanner?.existingUploadId}
        progress={mutation.isPending ? undefined : undefined}
      />
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
