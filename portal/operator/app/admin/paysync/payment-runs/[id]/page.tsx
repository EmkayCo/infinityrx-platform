"use client";
/**
 * /admin/paysync/payment-runs/[id] -- Single payment run detail + Manual AP form.
 * Fetches via TanStack Query from /api/paysync/payment-runs/[id] (BFF).
 * Renders PaymentRunDetailPage + ManualApForm from @infinityrx/module-paysync.
 * ManualApForm submits to POST /api/paysync/payment-runs/[id]/manual-ap — the
 * BFF gate on that route enforces billing_approver role before calling the backend.
 * Note: component prop is `run`, not `paymentRun`.
 */
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { PaymentRunDetailPage, ManualApForm } from "@infinityrx/module-paysync";
import type { ManualApEntry } from "@infinityrx/module-paysync";
import type { PaymentRun } from "@infinityrx/contract";

async function fetchPaymentRun(id: string): Promise<PaymentRun | null> {
  const res = await fetch(`/api/paysync/payment-runs/${encodeURIComponent(id)}`, {
    cache: "no-store",
  });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error("Failed to fetch payment run");
  return res.json() as Promise<PaymentRun>;
}

async function submitManualAp(id: string, entry: ManualApEntry): Promise<unknown> {
  const res = await fetch(
    `/api/paysync/payment-runs/${encodeURIComponent(id)}/manual-ap`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(entry),
    }
  );
  if (!res.ok) throw new Error("Failed to submit manual AP entry");
  return res.json();
}

export default function PaymentRunDetailRoute() {
  const params = useParams<{ id: string }>();
  const id = params.id ?? "";
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery<PaymentRun | null, Error>({
    queryKey: ["paysync", "payment-runs", id],
    queryFn: () => fetchPaymentRun(id),
    enabled: !!id,
    staleTime: 15_000,
  });

  const mutation = useMutation({
    mutationFn: (entry: ManualApEntry) => submitManualAp(id, entry),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["paysync", "payment-runs", id] });
    },
  });

  return (
    <div className="space-y-6 p-6">
      <PaymentRunDetailPage
        run={data ?? null}
        isLoading={isLoading}
        error={error?.message ?? null}
        currentRole="operator"
        onRelease={() => undefined}
      />
      <ManualApForm
        currentRole="operator"
        onSubmit={(entry) => mutation.mutate(entry)}
      />
    </div>
  );
}
