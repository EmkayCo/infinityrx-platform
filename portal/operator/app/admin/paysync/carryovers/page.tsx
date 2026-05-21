"use client";
/**
 * /admin/paysync/carryovers -- Paysync AP carryovers list.
 * Fetches via TanStack Query from /api/paysync/carryovers (BFF).
 * Renders CarryoversListPage from @infinityrx/module-paysync.
 */
import { useQuery } from "@tanstack/react-query";
import { CarryoversListPage } from "@infinityrx/module-paysync";
import type { Carryover, CarryoverListResponse } from "@infinityrx/contract";

async function fetchCarryovers(): Promise<CarryoverListResponse> {
  const res = await fetch("/api/paysync/carryovers", { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch carryovers");
  return res.json() as Promise<CarryoverListResponse>;
}

export default function CarryoversPage() {
  const { data, isLoading, error } = useQuery<CarryoverListResponse, Error>({
    queryKey: ["paysync", "carryovers"],
    queryFn: fetchCarryovers,
    staleTime: 15_000,
  });

  return (
    <div className="space-y-6 p-6">
      <CarryoversListPage
        carryovers={(data?.results ?? []) as ReadonlyArray<Carryover>}
        isLoading={isLoading}
        error={error?.message ?? null}
      />
    </div>
  );
}
