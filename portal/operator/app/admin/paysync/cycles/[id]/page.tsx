"use client";
/**
 * /admin/paysync/cycles/[id] -- Single billing cycle detail.
 * Fetches via TanStack Query from /api/paysync/cycles/[id] (BFF).
 * Renders CycleDetailPage from @infinityrx/module-paysync.
 */
import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { CycleDetailPage } from "@infinityrx/module-paysync";
import type { Cycle } from "@infinityrx/contract";

async function fetchCycle(id: string): Promise<Cycle | null> {
  const res = await fetch(`/api/paysync/cycles/${encodeURIComponent(id)}`, {
    cache: "no-store",
  });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error("Failed to fetch cycle");
  return res.json() as Promise<Cycle>;
}

export default function CycleDetailRoute() {
  const params = useParams<{ id: string }>();
  const id = params.id ?? "";

  const { data, isLoading, error } = useQuery<Cycle | null, Error>({
    queryKey: ["paysync", "cycles", id],
    queryFn: () => fetchCycle(id),
    enabled: !!id,
    staleTime: 15_000,
  });

  return (
    <div className="space-y-6 p-6">
      <CycleDetailPage
        cycle={data ?? null}
        isLoading={isLoading}
        error={error?.message ?? null}
        currentRole="operator"
        onClose={() => undefined}
      />
    </div>
  );
}
