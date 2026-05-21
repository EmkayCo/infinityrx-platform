"use client";
/**
 * /admin/paysync/carryovers/[id] -- Single AP carryover detail.
 * Fetches via TanStack Query from /api/paysync/carryovers/[id] (BFF).
 * Renders CarryoverDetailPage from @infinityrx/module-paysync.
 */
import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { CarryoverDetailPage } from "@infinityrx/module-paysync";
import type { Carryover } from "@infinityrx/contract";

async function fetchCarryover(id: string): Promise<Carryover | null> {
  const res = await fetch(`/api/paysync/carryovers/${encodeURIComponent(id)}`, {
    cache: "no-store",
  });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error("Failed to fetch carryover");
  return res.json() as Promise<Carryover>;
}

export default function CarryoverDetailRoute() {
  const params = useParams<{ id: string }>();
  const id = params.id ?? "";

  const { data, isLoading, error } = useQuery<Carryover | null, Error>({
    queryKey: ["paysync", "carryovers", id],
    queryFn: () => fetchCarryover(id),
    enabled: !!id,
    staleTime: 15_000,
  });

  return (
    <div className="space-y-6 p-6">
      <CarryoverDetailPage
        carryover={data ?? null}
        isLoading={isLoading}
        error={error?.message ?? null}
        currentRole="operator"
        onResolve={() => undefined}
      />
    </div>
  );
}
