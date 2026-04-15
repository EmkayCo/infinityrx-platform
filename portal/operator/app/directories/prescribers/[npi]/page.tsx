"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { AlertTriangle } from "lucide-react";
import dynamic from "next/dynamic";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { Skeleton } from "@shared/components/skeleton";
import { DataTable, type ColDef } from "@shared/components/data-table";
import { DollarDisplay } from "@shared/components/dollar-display";
import { apiGet, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import type { Prescriber } from "@shared/types/directories";
import { cn, formatDate } from "@shared/lib/format";
import { DetailPageLayout } from "@/components/ui/detail-page-layout";
import { InfoCard } from "@/components/ui/info-card";
import { StatusBadge, inferStatusVariant } from "@/components/ui/status-badge";

const DirectoriesPrescriberTopDrugsBar = dynamic(
  () =>
    import("@/components/charts/directories-prescriber-top-drugs-bar").then(
      (m) => m.DirectoriesPrescriberTopDrugsBar
    ),
  { ssr: false, loading: () => <Skeleton className="h-48" /> }
);

// ── Types ─────────────────────────────────────────────────────────────────────

interface ClaimRecord {
  id: string;
  date_of_service: string;
  pharmacy_name: string;
  drug_name: string;
  ndc: string;
  billed_amount: string;
  paid_amount: string;
  status: string;
}

interface PharmacyRow {
  npi: string;
  name: string;
  city: string;
  state: string;
  claim_count: number;
}

interface InvestigationRow {
  id: string;
  opened_at: string;
  category: string;
  status: string;
  flagged_amount: string;
}

// ── Column definitions ────────────────────────────────────────────────────────

const claimColumns: ColDef<ClaimRecord>[] = [
  { accessorKey: "date_of_service", header: "DOS", cell: (c) => formatDate(c.getValue() as string) },
  { accessorKey: "pharmacy_name", header: "Pharmacy" },
  { accessorKey: "drug_name", header: "Drug" },
  { accessorKey: "ndc", header: "NDC", cell: (c) => <span className="font-mono text-xs text-ifx-navy">{c.getValue() as string}</span> },
  { accessorKey: "billed_amount", header: "Billed", cell: (c) => <DollarDisplay amount={c.getValue() as string} size="sm" /> },
  { accessorKey: "paid_amount", header: "Paid", cell: (c) => <DollarDisplay amount={c.getValue() as string} size="sm" /> },
  { accessorKey: "status", header: "Status", cell: (c) => <StatusBadge status={c.getValue() as string} /> },
];

const pharmacyColumns: ColDef<PharmacyRow>[] = [
  { accessorKey: "npi", header: "NPI", cell: (c) => <span className="font-mono text-xs text-ifx-navy">{c.getValue() as string}</span> },
  { accessorKey: "name", header: "Name", cell: (c) => <span className="font-medium">{c.getValue() as string}</span> },
  { accessorKey: "city", header: "City" },
  { accessorKey: "state", header: "State" },
  { accessorKey: "claim_count", header: "Claims", cell: (c) => <span className="tabular-nums">{(c.getValue() as number).toLocaleString()}</span> },
];

const investigationColumns: ColDef<InvestigationRow>[] = [
  { accessorKey: "opened_at", header: "Opened", cell: (c) => formatDate(c.getValue() as string) },
  { accessorKey: "category", header: "Category" },
  { accessorKey: "status", header: "Status", cell: (c) => <StatusBadge status={c.getValue() as string} /> },
  { accessorKey: "flagged_amount", header: "Flagged", cell: (c) => <DollarDisplay amount={c.getValue() as string} size="sm" /> },
];

// ── Synthetic data ────────────────────────────────────────────────────────────

function hashNpi(npi: string): number {
  return npi.split("").reduce((s, c) => s + c.charCodeAt(0), 0);
}

function buildPrescriberClaims(npi: string): ClaimRecord[] {
  const seed = hashNpi(npi);
  const pharmacies = ["CVS Pharmacy #4521", "Walgreens #2819", "MedPlus Specialty Rx #105"];
  const drugs = [
    { name: "Atorvastatin 40mg", ndc: "0009373956" },
    { name: "Lisinopril 10mg", ndc: "0007102224" },
    { name: "Metformin 500mg", ndc: "0037846105" },
  ];
  return Array.from({ length: 10 }, (_, i) => {
    const drug = drugs[(seed + i) % drugs.length];
    return {
      id: `CLM-${String(seed + i * 100).padStart(8, "0")}`,
      date_of_service: new Date(Date.now() - i * 7 * 86400000).toISOString().substring(0, 10),
      pharmacy_name: pharmacies[(seed + i) % pharmacies.length],
      drug_name: drug.name,
      ndc: drug.ndc,
      billed_amount: (((seed + i * 31) % 400) + 50).toFixed(2),
      paid_amount: (((seed + i * 23) % 350) + 30).toFixed(2),
      status: i % 5 === 0 ? "reversed" : "paid",
    };
  });
}

function buildAffiliatedPharmacies(npi: string): PharmacyRow[] {
  const seed = hashNpi(npi);
  const cities = [
    { city: "Chicago", state: "IL" },
    { city: "Houston", state: "TX" },
    { city: "Phoenix", state: "AZ" },
  ];
  return Array.from({ length: 4 }, (_, i) => {
    const loc = cities[(seed + i) % cities.length];
    return {
      npi: `808${String(seed % 1000000 + i * 100).padStart(7, "0")}`,
      name: `${["CVS Pharmacy", "Walgreens", "MedPlus Rx", "Express Scripts"][i % 4]} #${(seed + i * 50) % 9999}`,
      city: loc.city,
      state: loc.state,
      claim_count: ((seed + i * 19) % 200) + 15,
    };
  });
}

function buildPrescriberInvestigations(npi: string): InvestigationRow[] {
  const seed = hashNpi(npi);
  const count = seed % 2;
  return Array.from({ length: count }, (_, i) => ({
    id: `INV-${String(seed + i * 3).padStart(6, "0")}`,
    opened_at: new Date(Date.now() - (i + 1) * 45 * 86400000).toISOString(),
    category: ["Prescribing Pattern", "Off-Label Use", "High Volume"][i % 3],
    status: ["open", "in_progress"][i % 2],
    flagged_amount: ((seed % 8000) + i * 1500 + 750).toFixed(2),
  }));
}

// ── Tabs ─────────────────────────────────────────────────────────────────────

type Tab = "claims" | "pharmacies" | "investigations";
const TABS: { id: Tab; label: string }[] = [
  { id: "claims", label: "Claims" },
  { id: "pharmacies", label: "Affiliated Pharmacies" },
  { id: "investigations", label: "Investigations" },
];

// ── Page ─────────────────────────────────────────────────────────────────────

export default function PrescriberDetailPage() {
  const { npi } = useParams<{ npi: string }>();
  const [activeTab, setActiveTab] = useState<Tab>("claims");

  const { data: prescriber, isLoading } = useQuery<Prescriber>({
    queryKey: ["prescriber", npi],
    queryFn: () =>
      apiGet<Prescriber>(
        buildUrl(`${API_URLS.prescriberDirectory}/api/v1/prescribers/${npi}`, {})
      ),
    staleTime: 60_000,
  });

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-64" />
        <div className="grid grid-cols-2 gap-4">
          <Skeleton className="h-40 rounded-lg" />
          <Skeleton className="h-40 rounded-lg" />
        </div>
      </div>
    );
  }

  if (!prescriber) {
    return <div className="p-6"><p className="text-ifx-gray-400">Prescriber not found.</p></div>;
  }

  const topDrugs = prescriber.prescribing_summary?.top_drugs ?? [];
  const claims = buildPrescriberClaims(npi);
  const pharmacies = buildAffiliatedPharmacies(npi);
  const investigations = buildPrescriberInvestigations(npi);

  const deaStatus = prescriber.dea_status;
  const licenseStatus = prescriber.state_license_status;

  return (
    <div className="p-6">
      <DetailPageLayout
        backLink={{ href: "/directories/prescribers", label: "Prescriber Directory" }}
        title={prescriber.full_name}
        subtitle={
          <span className="font-mono text-[13px]">
            {prescriber.specialty}
            {prescriber.subspecialty && ` · ${prescriber.subspecialty}`}
            {" · "}NPI: {prescriber.npi}
          </span>
        }
        actions={
          <div className="flex items-center gap-2">
            <StatusBadge
              status={licenseStatus}
              variant={inferStatusVariant(licenseStatus)}
            />
            {deaStatus === "active" && (
              <StatusBadge status="DEA Active" variant="success" />
            )}
            {deaStatus === "expired" && (
              <StatusBadge status="DEA Expired" variant="error" />
            )}
          </div>
        }
        summaryCards={[
          {
            label: "Claims (90d)",
            value: prescriber.prescribing_summary?.total_claims_90d ?? 0,
            format: "number" as const,
          },
          {
            label: "Avg Days Supply",
            value: prescriber.prescribing_summary?.avg_days_supply ?? 0,
            format: "raw" as const,
          },
          {
            label: "Top Drugs",
            value: topDrugs.length,
            format: "raw" as const,
          },
          {
            label: "Investigations",
            value: investigations.length,
            format: "raw" as const,
            accentColor: investigations.length > 0 ? "var(--ifx-warning)" : undefined,
          },
        ]}
        summaryColumns={4}
      >
        {/* Credential alerts */}
        {prescriber.credential_alerts.length > 0 && (
          <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle className="w-4 h-4 text-amber-600" />
              <span className="text-sm font-medium text-amber-800">Credential Alerts</span>
            </div>
            <ul className="space-y-1">
              {prescriber.credential_alerts.map((alert, i) => (
                <li key={i} className="text-xs text-amber-700 flex items-start gap-1.5">
                  <span className="mt-0.5">•</span>{alert}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Info cards */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <ErrorBoundary>
            <InfoCard
              title="Identity"
              columns={2}
              fields={[
                { label: "NPI", value: prescriber.npi, mono: true },
                { label: "Specialty", value: prescriber.specialty },
                { label: "Subspecialty", value: prescriber.subspecialty ?? null },
                { label: "Address", value: prescriber.address_line1 ?? null },
                { label: "City", value: prescriber.city ?? null },
                { label: "State", value: prescriber.state ?? null },
                { label: "Zip", value: prescriber.zip ?? null },
                { label: "Phone", value: prescriber.phone ?? null, mono: true },
              ]}
            />
          </ErrorBoundary>

          <ErrorBoundary>
            <InfoCard
              title="Credentials"
              columns={2}
              fields={[
                { label: "DEA Number", value: prescriber.dea_number ?? null, mono: true },
                { label: "DEA Status", value: prescriber.dea_status },
                { label: "DEA Expiry", value: prescriber.dea_expiry ?? null, format: "date" },
                { label: "State License", value: prescriber.state_license_number ?? null, mono: true },
                { label: "License Status", value: prescriber.state_license_status },
                { label: "License Expiry", value: prescriber.state_license_expiry ?? null, format: "date" },
              ]}
            />
          </ErrorBoundary>

          {/* Prescribing Patterns */}
          {prescriber.prescribing_summary && (
            <ErrorBoundary>
              <div className="rounded-lg bg-white ifx-card-shadow overflow-hidden lg:col-span-2">
                <header className="border-b border-ifx-gray-100 px-4 py-3">
                  <h3 className="text-sm font-bold text-ifx-gray-900">Prescribing Patterns</h3>
                </header>
                <div className="p-4">
                  <div className="grid grid-cols-2 gap-4 mb-4">
                    <div className="rounded-lg border border-ifx-gray-100 p-3">
                      <div className="text-[10px] font-semibold uppercase tracking-wider text-ifx-gray-400">Claims (90d)</div>
                      <div className="text-2xl font-bold text-ifx-gray-900 mt-1 tabular-nums">
                        {prescriber.prescribing_summary.total_claims_90d.toLocaleString()}
                      </div>
                    </div>
                    <div className="rounded-lg border border-ifx-gray-100 p-3">
                      <div className="text-[10px] font-semibold uppercase tracking-wider text-ifx-gray-400">Avg Days Supply</div>
                      <div className="text-2xl font-bold text-ifx-gray-900 mt-1 tabular-nums">
                        {prescriber.prescribing_summary.avg_days_supply}
                      </div>
                    </div>
                  </div>
                  {topDrugs.length > 0 && (
                    <>
                      <h4 className="text-sm font-semibold text-ifx-gray-900 mb-3">Top Prescribed Drugs (90 days)</h4>
                      <DirectoriesPrescriberTopDrugsBar data={topDrugs} />
                    </>
                  )}
                </div>
              </div>
            </ErrorBoundary>
          )}
        </div>

        {/* Tabs */}
        <ErrorBoundary>
          <div className="rounded-lg bg-white ifx-card-shadow overflow-hidden">
            <div className="flex border-b border-ifx-gray-100 overflow-x-auto">
              {TABS.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={cn(
                    "flex-shrink-0 px-4 py-3 text-sm font-medium transition-colors border-b-2",
                    activeTab === tab.id
                      ? "border-ifx-navy text-ifx-navy"
                      : "border-transparent text-ifx-gray-400 hover:text-ifx-gray-700"
                  )}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            <div className="p-4">
              {activeTab === "claims" && (
                <DataTable
                  columns={claimColumns}
                  data={claims}
                  isLoading={false}
                  emptyTitle="No claims found"
                  emptyDescription="No claims on file for this prescriber."
                />
              )}

              {activeTab === "pharmacies" && (
                <DataTable
                  columns={pharmacyColumns}
                  data={pharmacies}
                  isLoading={false}
                  emptyTitle="No pharmacies found"
                  emptyDescription="No affiliated pharmacies on file."
                />
              )}

              {activeTab === "investigations" && (
                <DataTable
                  columns={investigationColumns}
                  data={investigations}
                  isLoading={false}
                  emptyTitle="No investigations"
                  emptyDescription="No ReclaimRx investigations involving this prescriber."
                />
              )}
            </div>
          </div>
        </ErrorBoundary>
      </DetailPageLayout>
    </div>
  );
}
