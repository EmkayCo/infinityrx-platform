"use client";
/**
 * /admin/paysync/batches -- Paysync payment batches list.
 * Fetches via TanStack Query from /api/paysync/batches (BFF).
 * Renders BatchesListPage from @infinityrx/module-paysync.
 */
import { useQuery } from "@tanstack/react-query";
import { BatchesListPage } from "@infinityrx/module-paysync";
import type { Batch, BatchListResponse } from "@infinityrx/contract";

async function fetchBatches(): Promise<BatchListResponse> {
  const res = await fetch("/api/paysync/batches", { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch batches");
  return res.json() as Promise<BatchListResponse>;
}

export default function BatchesPage() {
  const { data, isLoading, error } = useQuery<BatchListResponse, Error>({
    queryKey: ["paysync", "batches"],
    queryFn: fetchBatches,
    staleTime: 15_000,
  });

  return (
    <div className="space-y-6 p-6">
      <BatchesListPage
        batches={(data?.results ?? []) as ReadonlyArray<Batch>}
        isLoading={isLoading}
        error={error?.message ?? null}
      />
    </div>
  );
}
