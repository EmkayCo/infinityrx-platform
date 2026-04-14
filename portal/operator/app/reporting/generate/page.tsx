"use client";

import React from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { ReportWizard } from "@/components/report-wizard";

export default function GenerateReportPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const templateId = searchParams.get("template") ?? undefined;

  return (
    <div className="p-6 h-full flex flex-col">
      <div className="flex-1 max-w-4xl mx-auto w-full" style={{ minHeight: "600px" }}>
        <ReportWizard
          initialTemplateId={templateId}
          onClose={() => router.push("/reporting")}
        />
      </div>
    </div>
  );
}
