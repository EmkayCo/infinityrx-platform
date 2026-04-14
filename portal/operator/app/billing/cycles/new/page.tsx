// New Billing Cycle — hosts the 6-step wizard.
"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { X } from "lucide-react";
import { BillingCycleWizard } from "@/components/billing-cycle-wizard";

export default function NewBillingCyclePage() {
  const router = useRouter();

  return (
    <div className="min-h-screen bg-ifx-bg-dark p-6">
      <div className="max-w-5xl mx-auto">
        <div className="flex items-center justify-between mb-5">
          <div>
            <h1 className="text-xl font-bold text-slate-100">New Billing Cycle</h1>
            <p className="text-sm text-slate-400 mt-0.5">
              Upload, map, validate, and approve a claims file to generate all billing outputs.
            </p>
          </div>
          <button
            onClick={() => router.push("/billing")}
            className="p-2 rounded-lg hover:bg-navy-700 text-slate-400 hover:text-slate-200 transition-colors"
            aria-label="Close wizard"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        <BillingCycleWizard />
      </div>
    </div>
  );
}
