"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import dynamic from "next/dynamic";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { Skeleton } from "@shared/components/skeleton";
import { DollarDisplay } from "@shared/components/dollar-display";
import { DataTable, type ColDef } from "@shared/components/data-table";
import { apiGet } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import type { Drug, DrugInteraction, TherapeuticEquivalent } from "@shared/types/directories";
import { cn, formatDate } from "@shared/lib/format";
import { DetailPageLayout } from "@/components/ui/detail-page-layout";
import { InfoCard } from "@/components/ui/info-card";
import { StatusBadge } from "@/components/ui/status-badge";

const DirectoriesDrugPriceHistoryLine = dynamic(
  () =>
    import("@/components/charts/directories-drug-price-history-line").then(
      (m) => m.DirectoriesDrugPriceHistoryLine
    ),
  { ssr: false, loading: () => <Skeleton className="h-48" /> }
);

// ── Types ─────────────────────────────────────────────────────────────────────

interface ClaimRecord {
  id: string;
  date_of_service: string;
  prescriber_name: string;
  pharmacy_name: string;
  billed_amount: string;
  paid_amount: string;
  status: string;
}

interface PrescriberRow {
  npi: string;
  full_name: string;
  specialty: string;
  claim_count: number;
}

interface PharmacyRow {
  npi: string;
  name: string;
  city: string;
  state: string;
  claim_count: number;
}

// ── Column definitions ────────────────────────────────────────────────────────

const SEVERITY_COLORS = {
  contraindicated: "bg-ifx-error-light text-ifx-error-text",
  major: "bg-ifx-error-light text-ifx-error-text",
  moderate: "bg-ifx-warning-light text-ifx-warning-text",
  minor: "bg-ifx-gray-100 text-ifx-gray-700",
};

const interactionColumns: ColDef<DrugInteraction>[] = [
  { accessorKey: "interacting_drug_name", header: "Drug", cell: (c) => <span className="font-medium text-sm">{c.getValue() as string}</span> },
  {
    accessorKey: "severity",
    header: "Severity",
    cell: (c) => (
      <span className={cn("text-xs px-2 py-0.5 rounded-full font-semibold capitalize", SEVERITY_COLORS[c.getValue() as keyof typeof SEVERITY_COLORS] ?? SEVERITY_COLORS.minor)}>
        {c.getValue() as string}
      </span>
    ),
  },
  { accessorKey: "description", header: "Description", cell: (c) => <span className="text-xs text-ifx-gray-400">{c.getValue() as string}</span> },
];

const equivColumns: ColDef<TherapeuticEquivalent>[] = [
  { accessorKey: "drug_name", header: "Drug", cell: (c) => <span className="font-medium text-sm">{c.getValue() as string}</span> },
  { accessorKey: "ndc", header: "NDC", cell: (c) => <span className="font-mono text-xs text-ifx-navy">{c.getValue() as string}</span> },
  { accessorKey: "manufacturer", header: "Manufacturer", cell: (c) => <span className="text-sm">{c.getValue() as string}</span> },
  { accessorKey: "awp", header: "AWP", cell: (c) => <DollarDisplay amount={c.getValue() as string} size="sm" /> },
];

const claimColumns: ColDef<ClaimRecord>[] = [
  { accessorKey: "date_of_service", header: "DOS", cell: (c) => formatDate(c.getValue() as string) },
  { accessorKey: "prescriber_name", header: "Prescriber" },
  { accessorKey: "pharmacy_name", header: "Pharmacy" },
  { accessorKey: "billed_amount", header: "Billed", cell: (c) => <DollarDisplay amount={c.getValue() as string} size="sm" /> },
  { accessorKey: "paid_amount", header: "Paid", cell: (c) => <DollarDisplay amount={c.getValue() as string} size="sm" /> },
  { accessorKey: "status", header: "Status", cell: (c) => <StatusBadge status={c.getValue() as string} /> },
];

const prescriberColumns: ColDef<PrescriberRow>[] = [
  { accessorKey: "npi", header: "NPI", cell: (c) => <span className="font-mono text-xs text-ifx-navy">{c.getValue() as string}</span> },
  { accessorKey: "full_name", header: "Name", cell: (c) => <span className="font-medium">{c.getValue() as string}</span> },
  { accessorKey: "specialty", header: "Specialty" },
  { accessorKey: "claim_count", header: "Claims", cell: (c) => <span className="tabular-nums">{(c.getValue() as number).toLocaleString()}</span> },
];

const pharmacyColumns: ColDef<PharmacyRow>[] = [
  { accessorKey: "npi", header: "NPI", cell: (c) => <span className="font-mono text-xs text-ifx-navy">{c.getValue() as string}</span> },
  { accessorKey: "name", header: "Name", cell: (c) => <span className="font-medium">{c.getValue() as string}</span> },
  { accessorKey: "city", header: "City" },
  { accessorKey: "state", header: "State" },
  { accessorKey: "claim_count", header: "Claims", cell: (c) => <span className="tabular-nums">{(c.getValue() as number).toLocaleString()}</span> },
];

// ── Synthetic data ────────────────────────────────────────────────────────────

function hashNdc(ndc: string): number {
  return ndc.split("").reduce((s, c) => s + c.charCodeAt(0), 0);
}

function buildDrugClaims(ndc: string): ClaimRecord[] {
  const seed = hashNdc(ndc);
  const prescribers = ["Dr. James Smith", "Dr. Mary Johnson", "Dr. Robert Williams"];
  const pharmacies = ["CVS Pharmacy #4521", "Walgreens #2819", "MedPlus Rx #105"];
  return Array.from({ length: 10 }, (_, i) => ({
    id: `CLM-${String(seed + i * 77).padStart(8, "0")}`,
    date_of_service: new Date(Date.now() - i * 7 * 86400000).toISOString().substring(0, 10),
    prescriber_name: prescribers[(seed + i) % prescribers.length],
    pharmacy_name: pharmacies[(seed + i) % pharmacies.length],
    billed_amount: (((seed + i * 37) % 400) + 80).toFixed(2),
    paid_amount: (((seed + i * 29) % 350) + 60).toFixed(2),
    status: i % 6 === 0 ? "reversed" : "paid",
  }));
}

function buildDrugPrescribers(ndc: string): PrescriberRow[] {
  const seed = hashNdc(ndc);
  const specialties = ["Internal Medicine", "Cardiology", "Family Medicine", "Oncology"];
  const names = ["Dr. James Smith", "Dr. Mary Johnson", "Dr. Robert Williams", "Dr. Patricia Brown", "Dr. John Jones"];
  return Array.from({ length: 5 }, (_, i) => ({
    npi: `190${String(seed % 1000000 + i * 47).padStart(7, "0")}`,
    full_name: names[i % names.length],
    specialty: specialties[i % specialties.length],
    claim_count: ((seed + i * 23) % 300) + 10,
  }));
}

function buildDrugPharmacies(ndc: string): PharmacyRow[] {
  const seed = hashNdc(ndc);
  const cities = [
    { city: "Chicago", state: "IL" },
    { city: "Houston", state: "TX" },
    { city: "Phoenix", state: "AZ" },
    { city: "Denver", state: "CO" },
  ];
  const names = ["CVS Pharmacy", "Walgreens", "MedPlus Specialty Rx", "Hometown Pharmacy"];
  return Array.from({ length: 4 }, (_, i) => {
    const loc = cities[(seed + i) % cities.length];
    return {
      npi: `808${String(seed % 1000000 + i * 83).padStart(7, "0")}`,
      name: `${names[i % names.length]} #${(seed + i * 61) % 9999}`,
      city: loc.city,
      state: loc.state,
      claim_count: ((seed + i * 41) % 250) + 5,
    };
  });
}

// ── Tabs ─────────────────────────────────────────────────────────────────────

type Tab = "claims" | "prescribers" | "pharmacies";
const TABS: { id: Tab; label: string }[] = [
  { id: "claims", label: "Claims" },
  { id: "prescribers", label: "Prescribers" },
  { id: "pharmacies", label: "Pharmacies" },
];

// ── Page ─────────────────────────────────────────────────────────────────────

export default function DrugDetailPage() {
  const { ndc } = useParams<{ ndc: string }>();
  const [activeTab, setActiveTab] = useState<Tab>("claims");

  const { data: drug, isLoading } = useQuery<Drug>({
    queryKey: ["drug", ndc],
    queryFn: () => apiGet<Drug>(`${API_URLS.drugDatabase}/api/v1/drugs/${ndc}`),
    staleTime: 60_000,
  });

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-64" />
        <div className="grid grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-24 rounded-lg" />)}
        </div>
        <Skeleton className="h-40 rounded-lg" />
      </div>
    );
  }

  if (!drug) return <div className="p-6"><p className="text-ifx-gray-400">Drug not found.</p></div>;

  const priceHistory = drug.pricing_history.map((p) => ({
    date: formatDate(p.recorded_at),
    AWP: parseFloat(p.awp),
    WAC: parseFloat(p.wac),
    NADAC: p.nadac ? parseFloat(p.nadac) : null,
  }));

  const claims = buildDrugClaims(ndc);
  const prescribers = buildDrugPrescribers(ndc);
  const pharmacies = buildDrugPharmacies(ndc);

  const headerBadges = (
    <div className="flex items-center gap-2 flex-wrap">
      <span
        className={cn(
          "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide",
          drug.brand_generic === "brand"
            ? "bg-ifx-primary-bg text-ifx-navy"
            : "bg-ifx-gray-100 text-ifx-gray-700"
        )}
        data-testid="brand-generic-badge"
      >
        {drug.brand_generic}
      </span>
      {drug.is_specialty && (
        <StatusBadge status="Specialty" variant="info" />
      )}
      {drug.rems_required && (
        <StatusBadge status={`REMS: ${drug.rems_program ?? "Required"}`} variant="warning" />
      )}
      {drug.is_controlled && (
        <StatusBadge status={`Schedule ${drug.schedule ?? "C"}`} variant="error" />
      )}
    </div>
  );

  return (
    <div className="p-6">
      <DetailPageLayout
        backLink={{ href: "/directories/drugs", label: "Drug Directory" }}
        eyebrow={drug.brand_name !== drug.generic_name ? drug.brand_name : undefined}
        title={drug.generic_name}
        subtitle={
          <span className="font-mono text-[13px]">
            {drug.strength} · {drug.dosage_form} · NDC: <span data-testid="drug-ndc">{drug.ndc}</span>
          </span>
        }
        actions={headerBadges}
        summaryCards={[
          { label: "AWP", value: drug.current_pricing.awp, format: "currency" as const },
          { label: "WAC", value: drug.current_pricing.wac, format: "currency" as const },
          ...(drug.current_pricing.mac ? [{ label: "MAC", value: drug.current_pricing.mac, format: "currency" as const }] : []),
          ...(drug.current_pricing.nadac ? [{ label: "NADAC", value: drug.current_pricing.nadac, format: "currency" as const }] : []),
        ]}
        summaryColumns={4}
      >
        {/* Identity & Classification info cards */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <ErrorBoundary>
            <InfoCard
              title="Identity"
              columns={2}
              fields={[
                { label: "NDC", value: drug.ndc, mono: true },
                { label: "Brand Name", value: drug.brand_name },
                { label: "Generic Name", value: drug.generic_name },
                { label: "Manufacturer", value: drug.manufacturer },
                { label: "Strength", value: drug.strength },
                { label: "Dosage Form", value: drug.dosage_form },
                { label: "Route", value: drug.route },
                { label: "Drug Category", value: drug.drug_category },
              ]}
            />
          </ErrorBoundary>

          <ErrorBoundary>
            <InfoCard
              title="Classification"
              columns={2}
              fields={[
                { label: "GPI", value: drug.gpi ?? null, mono: true },
                { label: "Therapeutic Class", value: drug.therapeutic_class },
                { label: "Brand / Generic", value: drug.brand_generic === "brand" ? "Brand" : "Generic" },
                { label: "Specialty Drug", value: drug.is_specialty ? "Yes" : "No" },
                { label: "Controlled", value: drug.is_controlled ? "Yes" : "No" },
                { label: "Schedule", value: drug.schedule ?? null },
                { label: "REMS Required", value: drug.rems_required ? "Yes" : "No" },
                { label: "REMS Program", value: drug.rems_program ?? null },
              ]}
            />
          </ErrorBoundary>
        </div>

        {/* Price History Chart */}
        {priceHistory.length > 0 && (
          <ErrorBoundary>
            <div className="rounded-lg bg-white ifx-card-shadow overflow-hidden">
              <header className="border-b border-ifx-gray-100 px-4 py-3">
                <h3 className="text-sm font-bold text-ifx-gray-900">Price Change History</h3>
              </header>
              <div className="p-4">
                <DirectoriesDrugPriceHistoryLine data={priceHistory} />
              </div>
            </div>
          </ErrorBoundary>
        )}

        {/* Interactions & Equivalents */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <ErrorBoundary>
            <div className="rounded-lg bg-white ifx-card-shadow overflow-hidden">
              <header className="border-b border-ifx-gray-100 px-4 py-3">
                <h3 className="text-sm font-bold text-ifx-gray-900">
                  Drug Interactions ({drug.interactions.length})
                </h3>
              </header>
              <div className="p-4">
                <DataTable
                  columns={interactionColumns}
                  data={drug.interactions}
                  emptyTitle="No known interactions"
                />
              </div>
            </div>
          </ErrorBoundary>

          <ErrorBoundary>
            <div className="rounded-lg bg-white ifx-card-shadow overflow-hidden">
              <header className="border-b border-ifx-gray-100 px-4 py-3">
                <h3 className="text-sm font-bold text-ifx-gray-900">
                  Therapeutic Equivalents ({drug.therapeutic_equivalents.length})
                </h3>
              </header>
              <div className="p-4">
                <DataTable
                  columns={equivColumns}
                  data={drug.therapeutic_equivalents}
                  emptyTitle="No therapeutic equivalents on file"
                />
              </div>
            </div>
          </ErrorBoundary>
        </div>

        {/* Tabs: Claims / Prescribers / Pharmacies */}
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
                  emptyDescription="No claims on file for this NDC."
                />
              )}

              {activeTab === "prescribers" && (
                <DataTable
                  columns={prescriberColumns}
                  data={prescribers}
                  isLoading={false}
                  emptyTitle="No prescribers found"
                  emptyDescription="No prescribers on file for this drug."
                />
              )}

              {activeTab === "pharmacies" && (
                <DataTable
                  columns={pharmacyColumns}
                  data={pharmacies}
                  isLoading={false}
                  emptyTitle="No pharmacies found"
                  emptyDescription="No dispensing pharmacies on file for this drug."
                />
              )}
            </div>
          </div>
        </ErrorBoundary>
      </DetailPageLayout>
    </div>
  );
}
