"use client";
/**
 * /admin/paysync/files -- Paysync generated file artifacts list.
 * Fetches via TanStack Query from /api/paysync/files (BFF).
 * Renders FilesListPage from @infinityrx/module-paysync.
 */
import { useQuery } from "@tanstack/react-query";
import { FilesListPage } from "@infinityrx/module-paysync";
import type { FileArtifact, FileArtifactListResponse } from "@infinityrx/contract";

async function fetchFiles(): Promise<FileArtifactListResponse> {
  const res = await fetch("/api/paysync/files", { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch files");
  return res.json() as Promise<FileArtifactListResponse>;
}

export default function FilesPage() {
  const { data, isLoading, error } = useQuery<FileArtifactListResponse, Error>({
    queryKey: ["paysync", "files"],
    queryFn: fetchFiles,
    staleTime: 15_000,
  });

  return (
    <div className="space-y-6 p-6">
      <FilesListPage
        files={(data?.results ?? []) as ReadonlyArray<FileArtifact>}
        isLoading={isLoading}
        error={error?.message ?? null}
      />
    </div>
  );
}
