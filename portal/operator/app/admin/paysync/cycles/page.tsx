"use client";
/**
 * /admin/paysync/cycles -- Paysync billing cycles list.
 * Fetches via TanStack Query from /api/paysync/cycles (BFF).
 * Renders CyclesListPage from @infinityrx/module-paysync.
 */
import { useQuery } from "@tanstack/react-query";
import { CyclesListPage } from "@infinityrx/module-paysync";
import type { Cycle, CycleListResponse } from "@infinityrx/contract";

async function fetchCycles(): Promise<CycleListResponse> {
  const res = await fetch("/api/paysync/cycles", { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch cycles");
  return res.json() as Promise<CycleListResponse>;
}

export default function CyclesPage() {
  const { data, isLoading, error } = useQuery<CycleListResponse, Error>({
    queryKey: ["paysync", "cycles"],
    queryFn: fetchCycles,
    staleTime: 15_000,
  });

  return (
    <div className="space-y-6 p-6">
      <CyclesListPage
        cycles={(data?.results ?? []) as ReadonlyArray<Cycle>}
        isLoading={isLoading}
        error={error?.message ?? null}
      />
    </div>
  );
}
