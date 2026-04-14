"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { ClientOnboardingWizard } from "@/components/client-onboarding-wizard";

export default function NewClientPage() {
  const router = useRouter();

  return (
    <div className="p-6 h-full">
      <div className="max-w-5xl mx-auto h-full">
        <ClientOnboardingWizard onClose={() => router.push("/admin/tenants")} />
      </div>
    </div>
  );
}
