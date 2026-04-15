"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { Shield } from "lucide-react";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { Skeleton } from "@shared/components/skeleton";
import { DataTable, type ColDef } from "@shared/components/data-table";
import { DollarDisplay } from "@shared/components/dollar-display";
import { apiGet, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import type { Pharmacy } from "@shared/types/directories";
import { cn, formatDate } from "@shared/lib/format";
import { DetailPageLayout } from "@/components/ui/detail-page-layout";
import { InfoCard } from "@/components/ui/info-card";
import { StatusBadge, inferStatusVariant } from "@/components/ui/status-badge";

// ── Types ─────────────────────────────────────────────────────────────────────

interface ClaimRecord {
  id: string;
  date_of_service: string;
  ndc: string;
  drug_name: string;
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

interface InvestigationRow {
  id: string;
  opened_at: string;
  category: string;
  status: string;
  flagged_amount: string;
}

interface DataQMetric {
  reject_code: string;
  description: string;
  count: number;
  pct: number;
}

interface PaymentRecord {
  payment_date: string;
  batch_id: string;
  claim_count: number;
  paid_amount: string;
  method: string;
}

// ── Column definitions ────────────────────────────────────────────────────────

const claimColumns: ColDef<ClaimRecord>[] = [
  { accessorKey: "date_of_service", header: "DOS", cell: (c) => formatDate(c.getValue() as string) },
  { accessorKey: "drug_name", header: "Drug" },
  { accessorKey: "ndc", header: "NDC", cell: (c) => <span className="font-mono text-xs text-ifx-navy">{c.getValue() as string}</span> },
  { accessorKey: "billed_amount", header: "Billed", cell: (c) => <DollarDisplay amount={c.getValue() as string} size="sm" /> },
  { accessorKey: "paid_amount", header: "Paid", cell: (c) => <DollarDisplay amount={c.getValue() as string} size="sm" /> },
  {
    accessorKey: "status",
    header: "Status",
    cell: (c) => <StatusBadge status={c.getValue() as string} />,
  },
];

const prescriberColumns: ColDef<PrescriberRow>[] = [
  { accessorKey: "npi", header: "NPI", cell: (c) => <span className="font-mono text-xs text-ifx-navy">{c.getValue() as string}</span> },
  { accessorKey: "full_name", header: "Name", cell: (c) => <span className="font-medium">{c.getValue() as string}</span> },
  { accessorKey: "specialty", header: "Specialty" },
  { accessorKey: "claim_count", header: "Claims", cell: (c) => <span className="tabular-nums">{(c.getValue() as number).toLocaleString()}</span> },
];

const investigationColumns: ColDef<InvestigationRow>[] = [
  { accessorKey: "opened_at", header: "Opened", cell: (c) => formatDate(c.getValue() as string) },
  { accessorKey: "category", header: "Category" },
  {
    accessorKey: "status",
    header: "Status",
    cell: (c) => <StatusBadge status={c.getValue() as string} />,
  },
  { accessorKey: "flagged_amount", header: "Flagged", cell: (c) => <DollarDisplay amount={c.getValue() as string} size="sm" /> },
];

const dataqColumns: ColDef<DataQMetric>[] = [
  { accessorKey: "reject_code", header: "Code", cell: (c) => <span className="font-mono text-xs text-ifx-navy">{c.getValue() as string}</span> },
  { accessorKey: "description", header: "Description" },
  { accessorKey: "count", header: "Count", cell: (c) => <span className="tabular-nums">{(c.getValue() as number).toLocaleString()}</span> },
  {
    accessorKey: "pct",
    header: "% of Claims",
    cell: (c) => <span className="tabular-nums">{(c.getValue() as number).toFixed(1)}%</span>,
  },
];

const paymentColumns: ColDef<PaymentRecord>[] = [
  { accessorKey: "payment_date", header: "Date", cell: (c) => formatDate(c.getValue() as string) },
  { accessorKey: "batch_id", header: "Batch ID", cell: (c) => <span className="font-mono text-xs text-ifx-navy">{c.getValue() as string}</span> },
  { accessorKey: "claim_count", header: "Claims", cell: (c) => <span className="tabular-nums">{(c.getValue() as number).toLocaleString()}</span> },
  { accessorKey: "paid_amount", header: "Paid", cell: (c) => <DollarDisplay amount={c.getValue() as string} size="sm" /> },
  { accessorKey: "method", header: "Method" },
];

// ── Synthetic tab data ────────────────────────────────────────────────────────

function hashNpi(npi: string): number {
  return npi.split("").reduce((s, c) => s + c.charCodeAt(0), 0);
}

function buildSyntheticPrescribers(npi: string): PrescriberRow[] {
  const seed = hashNpi(npi);
  const specialties = ["Internal Medicine", "Cardiology", "Family Medicine", "Oncology", "Endocrinology"];
  const names = ["Dr. James Smith", "Dr. Mary Johnson", "Dr. Robert Williams", "Dr. Patricia Brown", "Dr. John Jones"];
  return Array.from({ length: 5 }, (_, i) => ({
    npi: `190${String(seed % 1000000 + i).padStart(7, "0")}`,
    full_name: names[i % names.length],
    specialty: specialties[i % specialties.length],
    claim_count: ((seed + i * 17) % 400) + 10,
  }));
}

function buildSyntheticInvestigations(npi: string): InvestigationRow[] {
  const seed = hashNpi(npi);
  const categories = ["Billing Anomaly", "FWA Pattern", "Network Leakage", "Duplicate Claims"];
  const statuses = ["open", "in_progress", "closed", "escalated"];
  const count = seed % 3;
  return Array.from({ length: count }, (_, i) => ({
    id: `INV-${String(seed + i).padStart(6, "0")}`,
    opened_at: new Date(Date.now() - (i + 1) * 30 * 86400000).toISOString(),
    category: categories[i % categories.length],
    status: statuses[i % statuses.length],
    flagged_amount: ((seed % 5000) + i * 1000 + 500).toFixed(2),
  }));
}

function buildDataQMetrics(): DataQMetric[] {
  return [
    { reject_code: "07", description: "M/I Cardholder ID", count: 142, pct: 4.2 },
    { reject_code: "08", description: "M/I Person Code", count: 89, pct: 2.6 },
    { reject_code: "19", description: "M/I Days Supply", count: 67, pct: 2.0 },
    { reject_code: "70", description: "Drug Not Covered", count: 53, pct: 1.6 },
    { reject_code: "75", description: "Prior Auth Required", count: 31, pct: 0.9 },
  ];
}

function buildPaymentHistory(npi: string): PaymentRecord[] {
  const seed = hashNpi(npi);
  return Array.from({ length: 6 }, (_, i) => ({
    payment_date: new Date(Date.now() - (i + 1) * 30 * 86400000).toISOString().substring(0, 10),
    batch_id: `BATCH-${String(seed + i * 1000).padStart(8, "0")}`,
    claim_count: ((seed + i * 13) % 300) + 20,
    paid_amount: (((seed + i * 500) % 50000) + 5000).toFixed(2),
    method: i % 3 === 0 ? "ACH" : "Check",
  }));
}

// ── Risk score bar ────────────────────────────────────────────────────────────

function RiskBar({ label, score }: { label: string; score: number }) {
  const color =
    score >= 75 ? "bg-ifx-error" :
    score >= 50 ? "bg-ifx-warning" :
    "bg-ifx-success";
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs text-ifx-gray-700">{label}</span>
        <span className="text-xs font-semibold tabular-nums text-ifx-gray-900">{score}</span>
      </div>
      <div className="h-2 rounded-full bg-ifx-gray-100 overflow-hidden">
        <div className={cn("h-full rounded-full", color)} style={{ width: `${score}%` }} />
      </div>
    </div>
  );
}

// ── Tabs ─────────────────────────────────────────────────────────────────────

type Tab = "claims" | "prescribers" | "investigations" | "dataq" | "risk" | "financial";
const TABS: { id: Tab; label: string }[] = [
  { id: "claims", label: "Claims" },
  { id: "prescribers", label: "Prescribers" },
  { id: "investigations", label: "Investigations" },
  { id: "dataq", label: "DataQ" },
  { id: "risk", label: "Risk Analysis" },
  { id: "financial", label: "Financial" },
];

// ── Page ─────────────────────────────────────────────────────────────────────

export default function PharmacyDetailPage() {
  const { npi } = useParams<{ npi: string }>();
  const [activeTab, setActiveTab] = useState<Tab>("claims");

  const { data: pharmacy, isLoading } = useQuery<Pharmacy>({
    queryKey: ["pharmacy", npi],
    queryFn: () =>
      apiGet<Pharmacy>(`${API_URLS.pharmacyDirectory}/api/v1/pharmacies/${npi}`),
    staleTime: 60_000,
  });

  const { data: claims = [], isLoading: claimsLoading } = useQuery<ClaimRecord[]>({
    queryKey: ["pharmacy-claims", npi],
    queryFn: () =>
      apiGet<ClaimRecord[]>(
        buildUrl(`${API_URLS.pharmacyDirectory}/api/v1/pharmacies/${npi}/claims`, { limit: 50 })
      ),
    enabled: !!pharmacy && activeTab === "claims",
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

  if (!pharmacy) {
    return <div className="p-6"><p className="text-ifx-gray-400">Pharmacy not found.</p></div>;
  }

  const risk = pharmacy.risk_score;

  const summaryCards = [
    { label: "Total Claims", value: 3412, format: "number" as const },
    { label: "Total Paid", value: "248500.00", format: "currency" as const },
    { label: "Reversal Rate", value: 2.8, format: "percent" as const },
    {
      label: "Risk Score",
      value: risk?.overall ?? 0,
      format: "raw" as const,
      accentColor:
        (risk?.overall ?? 0) >= 75 ? "var(--ifx-error)" :
        (risk?.overall ?? 0) >= 50 ? "var(--ifx-warning)" :
        "var(--ifx-success)",
    },
  ];

  const statusActions = (
    <div className="flex items-center gap-2">
      <StatusBadge
        status={pharmacy.network_status.replace(/_/g, " ")}
        variant={
          pharmacy.network_status === "in_network" || pharmacy.network_status === "preferred"
            ? "success"
            : pharmacy.network_status === "pending"
              ? "warning"
              : pharmacy.network_status === "terminated"
                ? "error"
                : "neutral"
        }
      />
      <StatusBadge
        status={pharmacy.credentialing_status}
        variant={inferStatusVariant(pharmacy.credentialing_status)}
      />
      {pharmacy.is_340b && (
        <span
          className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide bg-ifx-primary-bg text-ifx-navy"
          data-testid="badge-340b"
        >
          <Shield className="w-3 h-3" />
          340B
        </span>
      )}
    </div>
  );

  const prescribers = buildSyntheticPrescribers(npi);
  const investigations = buildSyntheticInvestigations(npi);
  const dataqMetrics = buildDataQMetrics();
  const paymentHistory = buildPaymentHistory(npi);

  return (
    <div className="p-6">
      <DetailPageLayout
        backLink={{ href: "/directories/pharmacies", label: "Pharmacy Directory" }}
        title={pharmacy.name}
        subtitle={
          <span className="font-mono text-[13px]">
            NPI: {pharmacy.npi}
            {pharmacy.ncpdp_id && <> · NCPDP: {pharmacy.ncpdp_id}</>}
            {pharmacy.chain_code && <> · Chain: <span data-testid="chain-code">{pharmacy.chain_code}</span></>}
          </span>
        }
        actions={statusActions}
        summaryCards={summaryCards}
        summaryColumns={4}
      >
        {/* Info cards grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <ErrorBoundary>
            <InfoCard
              title="Identity"
              columns={2}
              fields={[
                { label: "NPI", value: pharmacy.npi, mono: true },
                { label: "NCPDP ID", value: pharmacy.ncpdp_id ?? null, mono: true },
                { label: "DEA Number", value: pharmacy.dea_number ?? null, mono: true },
                { label: "Store Number", value: pharmacy.store_number ?? null },
                { label: "Tax ID", value: pharmacy.tax_id ?? null, mono: true },
                { label: "NABP", value: pharmacy.nabp ?? null, mono: true },
              ]}
            />
          </ErrorBoundary>

          <ErrorBoundary>
            <InfoCard
              title="Chain & Network"
              columns={2}
              fields={[
                { label: "Chain Code", value: pharmacy.chain_code ?? null, mono: true },
                { label: "Pay-To Provider", value: pharmacy.pay_to_provider_name ?? null },
                { label: "Pay-To Provider ID", value: pharmacy.pay_to_provider_id ?? null, mono: true },
                { label: "Reconciliation Vendor", value: pharmacy.reconciliation_vendor ?? null },
                {
                  label: "Network Participation",
                  value: pharmacy.network_participation?.join(", ") ?? null,
                  span: 2,
                },
                { label: "Contract Effective", value: pharmacy.contract_effective_date ?? null, format: "date" },
                { label: "Contract Term", value: pharmacy.contract_term_date ?? null, format: "date" },
              ]}
            />
          </ErrorBoundary>

          <ErrorBoundary>
            <InfoCard
              title="Classification"
              columns={2}
              fields={[
                {
                  label: "Dispensing Class",
                  value: pharmacy.dispensing_class
                    ? pharmacy.dispensing_class === "340b"
                      ? "340B"
                      : pharmacy.dispensing_class.charAt(0).toUpperCase() + pharmacy.dispensing_class.slice(1)
                    : null,
                },
                { label: "Pharmacy Type", value: pharmacy.pharmacy_type.replace(/_/g, " ") },
                { label: "Billing Taxonomy", value: pharmacy.billing_taxonomy ?? null, mono: true },
                { label: "340B Status", value: pharmacy.is_340b ? "Enrolled" : "Not Enrolled" },
                {
                  label: "Specialty Designations",
                  value: pharmacy.specialty_designations?.join(", ") ?? "—",
                  span: 2,
                },
                { label: "Accepts Medicaid", value: pharmacy.accepts_medicaid ? "Yes" : "No" },
                { label: "Accepts Medicare", value: pharmacy.accepts_medicare ? "Yes" : "No" },
              ]}
            />
          </ErrorBoundary>

          <ErrorBoundary>
            <InfoCard
              title="Contact"
              columns={2}
              fields={[
                {
                  label: "Address",
                  value: `${pharmacy.address_line1}${pharmacy.address_line2 ? `, ${pharmacy.address_line2}` : ""}, ${pharmacy.city}, ${pharmacy.state} ${pharmacy.zip}`,
                  span: 2,
                },
                { label: "Phone", value: pharmacy.phone ?? null, mono: true },
                { label: "Fax", value: pharmacy.fax ?? null, mono: true },
                { label: "Email", value: pharmacy.email ?? null },
                { label: "Contact Person", value: pharmacy.contact_person ?? null },
              ]}
            />
          </ErrorBoundary>

          <ErrorBoundary>
            <div className="rounded-lg bg-white ifx-card-shadow overflow-hidden lg:col-span-2">
              <header className="flex items-center justify-between border-b border-ifx-gray-100 px-4 py-3">
                <h3 className="text-sm font-bold text-ifx-gray-900">Operational</h3>
              </header>
              <div className="p-4 space-y-4">
                {pharmacy.hours && (
                  <div>
                    <dt className="text-[10px] font-semibold uppercase tracking-wider text-ifx-gray-400 mb-1">Hours</dt>
                    <dd className="text-sm text-ifx-gray-900">{pharmacy.hours}</dd>
                  </div>
                )}
                {pharmacy.licenses && pharmacy.licenses.length > 0 && (
                  <div>
                    <dt className="text-[10px] font-semibold uppercase tracking-wider text-ifx-gray-400 mb-2">State Licenses</dt>
                    <div className="space-y-1.5">
                      {pharmacy.licenses.map((lic, idx) => (
                        <div key={idx} className="flex items-center justify-between text-sm">
                          <span className="font-mono text-ifx-gray-900">{lic.state} · {lic.license_number}</span>
                          <span className="flex items-center gap-2">
                            <StatusBadge status={lic.status} variant={inferStatusVariant(lic.status)} />
                            <span className="text-xs text-ifx-gray-400">Exp {lic.expiry}</span>
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {pharmacy.accreditations && pharmacy.accreditations.length > 0 && (
                  <div>
                    <dt className="text-[10px] font-semibold uppercase tracking-wider text-ifx-gray-400 mb-2">Accreditations</dt>
                    <div className="space-y-1.5">
                      {pharmacy.accreditations.map((acc, idx) => (
                        <div key={idx} className="flex items-center justify-between text-sm">
                          <span className="text-ifx-gray-900">{acc.body} — {acc.type}</span>
                          <span className="text-xs text-ifx-gray-400">Exp {acc.expiry}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                {!pharmacy.licenses?.length && !pharmacy.accreditations?.length && (
                  <p className="text-sm text-ifx-gray-400">No operational data on file.</p>
                )}
              </div>
            </div>
          </ErrorBoundary>
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
                  isLoading={claimsLoading}
                  emptyTitle="No claims found"
                  emptyDescription="No claims on file for this pharmacy."
                />
              )}

              {activeTab === "prescribers" && (
                <DataTable
                  columns={prescriberColumns}
                  data={prescribers}
                  isLoading={false}
                  emptyTitle="No prescribers found"
                  emptyDescription="No prescribers on file for this pharmacy."
                />
              )}

              {activeTab === "investigations" && (
                <DataTable
                  columns={investigationColumns}
                  data={investigations}
                  isLoading={false}
                  emptyTitle="No investigations"
                  emptyDescription="No ReclaimRx investigations involving this pharmacy."
                />
              )}

              {activeTab === "dataq" && (
                <div className="space-y-4">
                  <div className="grid grid-cols-3 gap-4">
                    {[
                      { label: "Rejection Rate", value: "7.3%", sub: "30-day avg" },
                      { label: "Field Completeness", value: "94.2%", sub: "all required fields" },
                      { label: "Avg Response Time", value: "1.4s", sub: "adjudication round-trip" },
                    ].map((kpi) => (
                      <div key={kpi.label} className="rounded-lg border border-ifx-gray-100 p-3">
                        <div className="text-[10px] font-semibold uppercase tracking-wider text-ifx-gray-400">{kpi.label}</div>
                        <div className="text-2xl font-bold text-ifx-gray-900 mt-1">{kpi.value}</div>
                        <div className="text-xs text-ifx-gray-400 mt-0.5">{kpi.sub}</div>
                      </div>
                    ))}
                  </div>
                  <h4 className="text-sm font-semibold text-ifx-gray-900">Top Reject Codes (90 days)</h4>
                  <DataTable
                    columns={dataqColumns}
                    data={dataqMetrics}
                    isLoading={false}
                    emptyTitle="No reject codes"
                    emptyDescription="No rejection data available."
                  />
                </div>
              )}

              {activeTab === "risk" && risk && (
                <div className="space-y-6">
                  <div className="flex items-center gap-4">
                    <div className="text-5xl font-bold tabular-nums text-ifx-gray-900">{risk.overall}</div>
                    <div>
                      <div className="text-sm font-medium text-ifx-gray-700">Overall Risk Score</div>
                      <StatusBadge
                        status={risk.overall >= 75 ? "High Risk" : risk.overall >= 50 ? "Medium Risk" : "Low Risk"}
                        variant={risk.overall >= 75 ? "error" : risk.overall >= 50 ? "warning" : "success"}
                      />
                    </div>
                  </div>
                  <div className="space-y-3">
                    <h4 className="text-sm font-semibold text-ifx-gray-900">Score Breakdown</h4>
                    <RiskBar label="Billing Anomaly" score={risk.billing_anomaly} />
                    <RiskBar label="Network Leakage" score={risk.network_leakage} />
                    <RiskBar label="Dispensing Pattern" score={risk.dispensing_pattern} />
                    <RiskBar label="Geographic Outlier" score={risk.geographic_outlier} />
                  </div>
                </div>
              )}
              {activeTab === "risk" && !risk && (
                <p className="text-sm text-ifx-gray-400">No risk score data available.</p>
              )}

              {activeTab === "financial" && (
                <div className="space-y-4">
                  <div className="grid grid-cols-3 gap-4">
                    {[
                      { label: "Avg Paid per Claim", value: "$72.84" },
                      { label: "Avg Copay Collected", value: "$15.20" },
                      { label: "Transaction Fee Avg", value: "$1.85" },
                    ].map((kpi) => (
                      <div key={kpi.label} className="rounded-lg border border-ifx-gray-100 p-3">
                        <div className="text-[10px] font-semibold uppercase tracking-wider text-ifx-gray-400">{kpi.label}</div>
                        <div className="text-2xl font-bold text-ifx-gray-900 mt-1">{kpi.value}</div>
                      </div>
                    ))}
                  </div>
                  <h4 className="text-sm font-semibold text-ifx-gray-900">Payment History</h4>
                  <DataTable
                    columns={paymentColumns}
                    data={paymentHistory}
                    isLoading={false}
                    emptyTitle="No payments"
                    emptyDescription="No payment history on file."
                  />
                </div>
              )}
            </div>
          </div>
        </ErrorBoundary>
      </DetailPageLayout>
    </div>
  );
}
