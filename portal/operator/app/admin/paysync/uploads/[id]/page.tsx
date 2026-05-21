"use client";
/**
 * /admin/paysync/uploads/[id] -- Single upload detail + claim viewer.
 * Fetches upload detail + claims via TanStack Query from BFF.
 * Renders UploadDetailPage (metadata, row errors) + UploadClaimViewer (paginated claims).
 */
import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import {
  UploadDetailPage,
  UploadClaimViewer,
} from "@infinityrx/module-paysync";
import type { Upload } from "@infinityrx/contract";

interface ClaimsResponse {
  readonly results: ReadonlyArray<Record<string, unknown>>;
  readonly total: number;
  readonly next_cursor?: string;
}

async function fetchUpload(id: string): Promise<Upload | null> {
  const res = await fetch(`/api/paysync/uploads/${encodeURIComponent(id)}`, {
    cache: "no-store",
  });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error("Failed to fetch upload");
  return res.json() as Promise<Upload>;
}

async function fetchClaims(id: string): Promise<ClaimsResponse> {
  const res = await fetch(`/api/paysync/uploads/${encodeURIComponent(id)}/claims`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error("Failed to fetch claims");
  return res.json() as Promise<ClaimsResponse>;
}

export default function UploadDetailPageRoute() {
  const params = useParams<{ id: string }>();
  const id = params.id ?? "";

  const uploadQuery = useQuery<Upload | null, Error>({
    queryKey: ["paysync", "uploads", id],
    queryFn: () => fetchUpload(id),
    enabled: !!id,
    staleTime: 15_000,
  });

  const claimsQuery = useQuery<ClaimsResponse, Error>({
    queryKey: ["paysync", "uploads", id, "claims"],
    queryFn: () => fetchClaims(id),
    enabled: !!id,
    staleTime: 15_000,
  });

  return (
    <div className="space-y-6 p-6">
      <UploadDetailPage
        upload={uploadQuery.data ?? null}
        isLoading={uploadQuery.isLoading}
        error={uploadQuery.error?.message ?? null}
        rowErrors={[]} // row_errors not yet in the Upload API response shape — intentional placeholder, track in backlog
      />
      <UploadClaimViewer
        uploadId={id}
        claims={claimsQuery.data?.results ?? []}
        isLoading={claimsQuery.isLoading}
        error={claimsQuery.error?.message ?? null}
        total={claimsQuery.data?.total ?? 0}
      />
    </div>
  );
}
