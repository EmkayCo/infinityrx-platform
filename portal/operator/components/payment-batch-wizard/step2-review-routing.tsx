// Step 2 — Review Routing
"use client";

import React, { useEffect, useState } from "react";
import { previewRouting } from "@shared/lib/payments-api";
import { DollarDisplay } from "@shared/components/dollar-display";
import { Skeleton } from "@shared/components/skeleton";
import { cn } from "@shared/lib/format";
import Decimal from "decimal.js";
import { PaymentBatchWizardData } from "./types";
import type { BatchRouting, VendorType } from "@shared/types/payments";

interface ReviewRoutingStepProps {
  data: PaymentBatchWizardData;
  onChange: (partial: Partial<PaymentBatchWizardData>) => void;
}

const VENDOR_LABELS: Record<VendorType, string> = {
  nacha: "NACHA ACH",
  echo: "Echo Healthcare",
  check_issuing: "CheckIssuing",
  wire: "Wire Transfer",
};

const VENDOR_COLORS: Record<VendorType, string> = {
  nacha: "bg-teal-500/10 border-teal-500/30 text-teal-400",
  echo: "bg-blue-500/10 border-blue-500/30 text-blue-400",
  check_issuing: "bg-purple-500/10 border-purple-500/30 text-purple-400",
  wire: "bg-yellow-500/10 border-yellow-500/30 text-yellow-400",
};

export function ReviewRoutingStep({ data, onChange }: ReviewRoutingStepProps) {
  const [loading, setLoading] = useState(data.routing_summary.length === 0);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (data.routing_summary.length > 0) return;
    if (data.selected_claim_ids.length === 0) {
      setLoading(false);
      return;
    }
    previewRouting(data.selected_claim_ids)
      .then((routing: BatchRouting[]) => {
        onChange({ routing_summary: routing });
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Failed to load routing");
      })
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (loading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded border border-red-500/30 bg-red-500/5 p-3">
        <p className="text-sm text-red-400">{error}</p>
      </div>
    );
  }

  // Group by vendor
  const byVendor = data.routing_summary.reduce<Record<string, BatchRouting[]>>(
    (acc, r) => {
      if (!acc[r.vendor]) acc[r.vendor] = [];
      acc[r.vendor].push(r);
      return acc;
    },
    {}
  );

  return (
    <div className="space-y-5">
      <p className="text-sm text-slate-400">
        Payment routing is determined by client configuration. Review vendor assignments before generating files.
      </p>

      {/* Summary cards per vendor */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        {Object.entries(byVendor).map(([vendor, routes]) => {
          const totalAmount = routes
            .reduce(
              (sum, r) => sum.plus(new Decimal(r.total_amount)),
              new Decimal(0)
            )
            .toFixed(2);
          const vendorLabel =
            VENDOR_LABELS[vendor as VendorType] ?? vendor;
          const colorClass =
            VENDOR_COLORS[vendor as VendorType] ??
            "bg-slate-500/10 border-slate-500/30 text-slate-400";

          return (
            <div
              key={vendor}
              className={cn(
                "rounded-lg border p-4 space-y-3",
                colorClass
              )}
            >
              <div className="flex items-center justify-between">
                <span className="font-semibold text-sm">{vendorLabel}</span>
                <span className="text-xs bg-white/10 rounded px-2 py-0.5">
                  {routes.length} client{routes.length !== 1 ? "s" : ""}
                </span>
              </div>
              <DollarDisplay amount={totalAmount} size="lg" showScale />
              <div className="space-y-1">
                {routes.map((r) => (
                  <div
                    key={r.client_id}
                    className="flex items-center justify-between text-xs text-current/70"
                  >
                    <span>{r.client_name}</span>
                    <span className="tabular-nums">
                      {r.payment_count} pmts
                    </span>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {/* Flat list */}
      {data.routing_summary.length > 0 && (
        <div className="rounded-lg border border-ifx-border-dark overflow-hidden">
          <div className="grid grid-cols-[1fr_auto_auto_auto] gap-3 px-4 py-2 bg-navy-900/80 text-xs font-semibold text-slate-400 uppercase tracking-wide border-b border-ifx-border-dark">
            <span>Client</span>
            <span>Vendor</span>
            <span className="text-right">Payments</span>
            <span className="text-right">Amount</span>
          </div>
          <div className="divide-y divide-ifx-border-dark/50">
            {data.routing_summary.map((r, i) => (
              <div
                key={i}
                className="grid grid-cols-[1fr_auto_auto_auto] gap-3 items-center px-4 py-2.5"
              >
                <span className="text-sm text-slate-200">{r.client_name}</span>
                <span className="text-xs px-2 py-0.5 rounded bg-navy-700 text-slate-300">
                  {VENDOR_LABELS[r.vendor] ?? r.vendor}
                </span>
                <span className="text-sm text-slate-400 text-right tabular-nums">
                  {r.payment_count}
                </span>
                <DollarDisplay amount={r.total_amount} size="sm" />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
