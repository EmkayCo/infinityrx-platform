"use client";
/**
 * /admin/paysync/files/[id] -- Single file artifact detail.
 * Fetches via TanStack Query from /api/paysync/files/[id] (BFF).
 * Renders FileDetailPage from @infinityrx/module-paysync.
 */
import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { FileDetailPage } from "@infinityrx/module-paysync";
import type { FileArtifact } from "@infinityrx/contract";

async function fetchFile(id: string): Promise<FileArtifact | null> {
  const res = await fetch(`/api/paysync/files/${encodeURIComponent(id)}`, {
    cache: "no-store",
  });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error("Failed to fetch file");
  return res.json() as Promise<FileArtifact>;
}

export default function FileDetailRoute() {
  const params = useParams<{ id: string }>();
  const id = params.id ?? "";

  const { data, isLoading, error } = useQuery<FileArtifact | null, Error>({
    queryKey: ["paysync", "files", id],
    queryFn: () => fetchFile(id),
    enabled: !!id,
    staleTime: 15_000,
  });

  return (
    <div className="space-y-6 p-6">
      <FileDetailPage
        file={data ?? null}
        isLoading={isLoading}
        error={error?.message ?? null}
      />
    </div>
  );
}
