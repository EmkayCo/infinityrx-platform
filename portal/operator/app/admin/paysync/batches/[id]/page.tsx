"use client";
/**
 * /admin/paysync/batches/[id] -- Single payment batch detail.
 * Fetches via TanStack Query from /api/paysync/batches/[id] (BFF).
 * Renders BatchDetailPage from @infinityrx/module-paysync.
 */
import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { BatchDetailPage } from "@infinityrx/module-paysync";
import type { Batch } from "@infinityrx/contract";

async function fetchBatch(id: string): Promise<Batch | null> {
  const res = await fetch(`/api/paysync/batches/${encodeURIComponent(id)}`, {
    cache: "no-store",
  });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error("Failed to fetch batch");
  return res.json() as Promise<Batch>;
}

export default function BatchDetailRoute() {
  const params = useParams<{ id: string }>();
  const id = params.id ?? "";

  const { data, isLoading, error } = useQuery<Batch | null, Error>({
    queryKey: ["paysync", "batches", id],
    queryFn: () => fetchBatch(id),
    enabled: !!id,
    staleTime: 15_000,
  });

  return (
    <div className="space-y-6 p-6">
      <BatchDetailPage
        batch={data ?? null}
        isLoading={isLoading}
        error={error?.message ?? null}
        currentRole="operator"
        onRelease={() => undefined}
        onHold={() => undefined}
      />
    </div>
  );
}
