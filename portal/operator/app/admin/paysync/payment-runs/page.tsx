"use client";
/**
 * /admin/paysync/payment-runs -- Paysync payment runs list.
 * Fetches via TanStack Query from /api/paysync/payment-runs (BFF).
 * Renders PaymentRunsListPage from @infinityrx/module-paysync.
 * Note: component prop is `runs`, not `paymentRuns`.
 */
import { useQuery } from "@tanstack/react-query";
import { PaymentRunsListPage } from "@infinityrx/module-paysync";
import type { PaymentRun, PaymentRunListResponse } from "@infinityrx/contract";

async function fetchPaymentRuns(): Promise<PaymentRunListResponse> {
  const res = await fetch("/api/paysync/payment-runs", { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch payment runs");
  return res.json() as Promise<PaymentRunListResponse>;
}

export default function PaymentRunsPage() {
  const { data, isLoading, error } = useQuery<PaymentRunListResponse, Error>({
    queryKey: ["paysync", "payment-runs"],
    queryFn: fetchPaymentRuns,
    staleTime: 15_000,
  });

  return (
    <div className="space-y-6 p-6">
      <PaymentRunsListPage
        runs={(data?.results ?? []) as ReadonlyArray<PaymentRun>}
        isLoading={isLoading}
        error={error?.message ?? null}
      />
    </div>
  );
}
