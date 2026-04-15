"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { useState } from "react";
import { Flag, FileSearch, Package, AlertCircle } from "lucide-react";
import { apiGet } from "@shared/lib/api-client";
import { DetailPageLayout } from "@/components/ui/detail-page-layout";
import { InfoCard } from "@/components/ui/info-card";
import { StatusBadge } from "@/components/ui/status-badge";
import { ConfigurableDataTable, type Column } from "@/components/ui/configurable-data-table";
import { cn } from "@shared/lib/format";

interface MockClaim {
  id: string;
  tenant_id?: string;
  cycle_id?: string;
  client_id?: string;
  client_name?: string;
  program_id?: string;
  program_name?: string;
  pharmacy_npi?: string;
  pharmacy_name?: string;
  member_id?: string;
  drug_ndc?: string;
  drug_name?: string;
  fill_date?: string;
  quantity?: string | number;
  days_supply?: number;
  ingredient_cost?: string;
  dispensing_fee?: string;
  copay?: string;
  plan_paid?: string;
  status?: string;
  rejection_reason?: string | null;
  created_at?: string;
  // Extended fields that may be present on richer records:
  auth_number?: string;
  rx_number?: string;
  fill_number?: number;
  date_of_service?: string;
  place_of_service?: string;
  emergency_indicator?: boolean;
  cpt_code?: string;
  diagnosis_codes?: string[];
  units?: number;
  sales_tax?: string;
  patient_paid?: string;
  total_paid?: string;
  pos_adjustment?: string;
  debit_card_amount?: string;
  transaction_fee?: string;
  incentive_fee?: string;
  copay_assistance_amount?: string;
  card_bin?: string;
  card_pcn?: string;
  card_group?: string;
  remaining_benefit?: string;
  enrollment_date?: string;
  patient?: {
    cardholder_id?: string;
    first_name?: string;
    last_name?: string;
    dob?: string;
    sex?: string;
    address?: string;
    city?: string;
    state?: string;
    zip?: string;
    phone?: string;
    email?: string;
    mrn?: string;
  };
  billing_provider?: {
    npi?: string;
    tax_id?: string;
    name?: string;
    address?: string;
    phone?: string;
    fax?: string;
    email?: string;
  };
  service_provider?: {
    npi?: string;
    name?: string;
    address?: string;
  };
  reversal_chain?: { id: string; type: string; date: string }[];
  attachments?: { id: string; name: string; uploaded_at: string }[];
  investigation_id?: string;
  related_claims?: MockClaim[];
  other_coverage_code?: string;
  bin?: string;
  insurance_type?: string;
  insured_id?: string;
  policy_group?: string;
  plan_name?: string;
  group_id?: string;
}

type TabId = "reversal" | "related" | "investigation" | "attachments";

const TABS: { id: TabId; label: string }[] = [
  { id: "reversal", label: "Reversal History" },
  { id: "related", label: "Related Claims" },
  { id: "investigation", label: "Investigation" },
  { id: "attachments", label: "Attachments" },
];

export default function ClaimDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [activeTab, setActiveTab] = useState<TabId>("reversal");

  const { data: claim, isLoading, error } = useQuery<MockClaim>({
    queryKey: ["claim", id],
    queryFn: () => apiGet<MockClaim>(`/billing/v1/claims/${id}`),
    enabled: !!id,
  });

  if (isLoading) {
    return (
      <DetailPageLayout
        backLink={{ href: "/claims", label: "Back to Claims" }}
        title="Loading claim…"
      >
        <div className="h-40 rounded-lg bg-white shimmer" />
      </DetailPageLayout>
    );
  }

  if (error || !claim) {
    return (
      <DetailPageLayout
        backLink={{ href: "/claims", label: "Back to Claims" }}
        title="Claim not found"
      >
        <div className="flex items-center gap-2 rounded-md bg-ifx-error-light border border-ifx-error/20 p-4 text-sm text-ifx-error">
          <AlertCircle className="h-4 w-4" />
          We couldn&apos;t find a claim with ID <span className="font-mono">{id}</span>.
        </div>
      </DetailPageLayout>
    );
  }

  const displayTitle = claim.auth_number
    ? `Auth #${claim.auth_number}`
    : `Claim #${claim.id.slice(0, 8)}`;

  const subtitle = (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
      {claim.drug_name && (
        <span className="font-medium text-ifx-gray-700">{claim.drug_name}</span>
      )}
      {claim.pharmacy_name && <span>· {claim.pharmacy_name}</span>}
      {claim.status && (
        <StatusBadge status={claim.status} />
      )}
    </div>
  );

  return (
    <DetailPageLayout
      backLink={{ href: "/claims", label: "Back to Claims" }}
      eyebrow="Claim Detail"
      title={displayTitle}
      subtitle={subtitle}
      actions={
        <>
          <ActionButton icon={<Flag className="h-3.5 w-3.5" />} label="Flag for Review" />
          <ActionButton
            icon={<FileSearch className="h-3.5 w-3.5" />}
            label="Create Investigation"
          />
          <ActionButton
            icon={<Package className="h-3.5 w-3.5" />}
            label="View in Batch"
          />
        </>
      }
      summaryCards={[
        {
          label: "Total Paid",
          value: claim.total_paid ?? sumAmounts(claim.plan_paid, claim.copay) ?? "0",
          format: "currency",
          accentColor: "var(--ifx-navy)",
        },
        {
          label: "Patient Responsibility",
          value: claim.patient_paid ?? claim.copay ?? "0",
          format: "currency",
          accentColor: "var(--ifx-blue)",
        },
        {
          label: "Copay Assistance",
          value: claim.copay_assistance_amount ?? "0",
          format: "currency",
          accentColor: "var(--ifx-blue)",
        },
        {
          label: "Status",
          value: (claim.status ?? "—").toUpperCase(),
          format: "raw",
          accentColor: "var(--ifx-success)",
        },
      ]}
    >
      {/* Info cards grid */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <InfoCard
          title="Patient Information"
          fields={[
            { label: "Cardholder ID", value: claim.patient?.cardholder_id ?? claim.member_id, mono: true },
            { label: "First Name", value: claim.patient?.first_name },
            { label: "Last Name", value: claim.patient?.last_name },
            { label: "Date of Birth", value: claim.patient?.dob, format: "date" },
            { label: "Sex", value: claim.patient?.sex },
            { label: "Address", value: claim.patient?.address, span: 2 },
            { label: "City", value: claim.patient?.city },
            { label: "State", value: claim.patient?.state },
            { label: "ZIP", value: claim.patient?.zip },
            { label: "Phone", value: claim.patient?.phone, format: "phone" },
            { label: "Email", value: claim.patient?.email, span: 2 },
            { label: "MRN / Account #", value: claim.patient?.mrn, mono: true },
            { label: "Claim ID", value: claim.id, mono: true },
          ]}
        />

        <InfoCard
          title="Provider Information"
          fields={[
            { label: "Billing Provider NPI", value: claim.billing_provider?.npi ?? claim.pharmacy_npi, format: "npi", mono: true },
            { label: "Federal Tax ID", value: claim.billing_provider?.tax_id, mono: true },
            { label: "Billing Provider Name", value: claim.billing_provider?.name ?? claim.pharmacy_name, span: 2 },
            { label: "Address", value: claim.billing_provider?.address, span: 2 },
            { label: "Phone", value: claim.billing_provider?.phone, format: "phone" },
            { label: "Fax", value: claim.billing_provider?.fax, format: "phone" },
            { label: "Email", value: claim.billing_provider?.email, span: 2 },
            { label: "Service Provider NPI", value: claim.service_provider?.npi, format: "npi", mono: true },
            { label: "Service Provider Name", value: claim.service_provider?.name, span: 2 },
            { label: "Service Provider Address", value: claim.service_provider?.address, span: 2 },
          ]}
        />
      </div>

      <InfoCard
        title="Claim Information"
        columns={3}
        fields={[
          { label: "Rx Number", value: claim.rx_number, mono: true },
          { label: "Claim Type", value: "Pharmacy" },
          { label: "Claim Disposition", value: claim.status },
          { label: "Status", value: claim.status ? <StatusBadge status={claim.status} /> : null },
          { label: "Date Added", value: claim.created_at, format: "date" },
          { label: "Other Coverage Code", value: claim.other_coverage_code },
          { label: "IFX Group ID", value: claim.group_id, mono: true },
          { label: "BIN / Other Payer ID", value: claim.bin ?? claim.card_bin, mono: true },
          { label: "Insurance Type", value: claim.insurance_type },
          { label: "Insured's ID", value: claim.insured_id, mono: true },
          { label: "Policy Group", value: claim.policy_group },
          { label: "Plan Name", value: claim.plan_name ?? claim.program_name },
          { label: "Fill Number", value: claim.fill_number },
          { label: "Reject Reason", value: claim.rejection_reason },
          { label: "Date of Service (from)", value: claim.date_of_service ?? claim.fill_date, format: "date" },
          { label: "Date of Service (to)", value: claim.date_of_service ?? claim.fill_date, format: "date" },
          { label: "Place of Service", value: claim.place_of_service },
          { label: "Emergency Indicator", value: claim.emergency_indicator ? "Yes" : "No" },
          { label: "NDC", value: claim.drug_ndc, format: "ndc", mono: true },
          { label: "Drug Name", value: claim.drug_name, span: 2 },
          { label: "CPT / HCPCS / JCode", value: claim.cpt_code, mono: true },
          { label: "JCode Modifier", value: undefined },
          { label: "Diagnosis Codes", value: claim.diagnosis_codes?.join(", "), mono: true },
          { label: "Units", value: claim.units, format: "number" },
          { label: "Days Supply", value: claim.days_supply, format: "number" },
          { label: "Quantity", value: claim.quantity, format: "number" },
        ]}
      />

      <InfoCard
        title="Financial"
        columns={3}
        fields={[
          { label: "Ingredient Cost", value: claim.ingredient_cost, format: "currency" },
          { label: "Dispensing Fee", value: claim.dispensing_fee, format: "currency" },
          { label: "Sales Tax", value: claim.sales_tax, format: "currency" },
          { label: "Copay Amount", value: claim.copay, format: "currency" },
          { label: "Patient Paid", value: claim.patient_paid, format: "currency" },
          { label: "Plan Paid", value: claim.plan_paid, format: "currency" },
          { label: "Total Paid", value: claim.total_paid ?? sumAmounts(claim.plan_paid, claim.copay) ?? "", format: "currency" },
          { label: "POS Adjustment", value: claim.pos_adjustment, format: "currency" },
          { label: "Debit Card Amount", value: claim.debit_card_amount, format: "currency" },
          { label: "Transaction Fee", value: claim.transaction_fee, format: "currency" },
          { label: "Incentive Fee", value: claim.incentive_fee, format: "currency" },
        ]}
      />

      {(claim.program_name || claim.copay_assistance_amount) && (
        <InfoCard
          title="Copay Program"
          columns={3}
          fields={[
            { label: "Program Name", value: claim.program_name, span: 2 },
            { label: "Enrollment Date", value: claim.enrollment_date, format: "date" },
            { label: "Card BIN", value: claim.card_bin, mono: true },
            { label: "Card PCN", value: claim.card_pcn, mono: true },
            { label: "Card Group", value: claim.card_group, mono: true },
            { label: "Copay Assistance Amount", value: claim.copay_assistance_amount, format: "currency" },
            { label: "Remaining Benefit", value: claim.remaining_benefit, format: "currency" },
          ]}
        />
      )}

      {/* Tabs */}
      <div className="flex flex-col gap-3">
        <div
          role="tablist"
          className="flex items-center gap-1 border-b border-ifx-gray-100"
        >
          {TABS.map((tab) => (
            <button
              key={tab.id}
              role="tab"
              aria-selected={activeTab === tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "relative px-4 py-2 text-sm font-medium transition-colors",
                activeTab === tab.id
                  ? "text-ifx-gray-900"
                  : "text-ifx-gray-400 hover:text-ifx-gray-700",
              )}
            >
              {tab.label}
              {activeTab === tab.id && (
                <span className="absolute inset-x-4 bottom-0 h-0.5 rounded-t bg-ifx-blue" />
              )}
            </button>
          ))}
        </div>

        <div className="rounded-lg bg-white ifx-card-shadow p-4">
          {activeTab === "reversal" && <ReversalTab claim={claim} />}
          {activeTab === "related" && <RelatedTab claim={claim} />}
          {activeTab === "investigation" && <InvestigationTab claim={claim} />}
          {activeTab === "attachments" && <AttachmentsTab claim={claim} />}
        </div>
      </div>
    </DetailPageLayout>
  );
}

function ActionButton({ icon, label }: { icon: React.ReactNode; label: string }) {
  return (
    <button
      type="button"
      className="inline-flex items-center gap-1.5 rounded-md border border-ifx-gray-100 bg-white px-3 py-1.5 text-xs font-medium text-ifx-gray-700 hover:bg-ifx-gray-50 transition-colors"
    >
      {icon}
      {label}
    </button>
  );
}

function sumAmounts(a?: string, b?: string): string | undefined {
  if (!a && !b) return undefined;
  const na = Number(a ?? 0);
  const nb = Number(b ?? 0);
  if (Number.isNaN(na) || Number.isNaN(nb)) return undefined;
  return (na + nb).toFixed(2);
}

function ReversalTab({ claim }: { claim: MockClaim }) {
  const chain = claim.reversal_chain ?? [];
  if (chain.length === 0) {
    return (
      <div className="text-sm text-ifx-gray-400">
        This claim has no reversal history.
      </div>
    );
  }
  return (
    <ol className="space-y-2">
      {chain.map((entry) => (
        <li
          key={entry.id}
          className="flex items-center gap-3 rounded-md border border-ifx-gray-100 px-3 py-2 text-sm"
        >
          <StatusBadge status={entry.type} />
          <span className="font-mono text-[13px] text-ifx-gray-700">{entry.id}</span>
          <span className="ml-auto text-ifx-gray-400">{entry.date}</span>
        </li>
      ))}
    </ol>
  );
}

function RelatedTab({ claim }: { claim: MockClaim }) {
  const related = claim.related_claims ?? [];
  const columns: Column<MockClaim>[] = [
    { id: "fill_date", header: "Fill Date", accessor: (r) => r.fill_date, format: "date" },
    { id: "drug_name", header: "Drug", accessor: (r) => r.drug_name },
    { id: "pharmacy_name", header: "Pharmacy", accessor: (r) => r.pharmacy_name },
    { id: "status", header: "Status", accessor: (r) => r.status, format: "status" },
    { id: "plan_paid", header: "Plan Paid", accessor: (r) => r.plan_paid, format: "currency", align: "right" },
  ];

  if (related.length === 0) {
    return (
      <div className="text-sm text-ifx-gray-400">
        No related claims found for this patient, drug, or pharmacy.
      </div>
    );
  }
  return (
    <ConfigurableDataTable
      tableId="claim-detail-related"
      columns={columns}
      data={related}
      getRowId={(row) => row.id}
      exportable={false}
    />
  );
}

function InvestigationTab({ claim }: { claim: MockClaim }) {
  if (!claim.investigation_id) {
    return (
      <div className="text-sm text-ifx-gray-400">
        This claim is not linked to any ReclaimRx investigation.
      </div>
    );
  }
  return (
    <div className="text-sm">
      Linked to investigation{" "}
      <a
        href={`/reclaimrx/investigations/${claim.investigation_id}`}
        className="font-semibold text-ifx-blue hover:underline"
      >
        {claim.investigation_id}
      </a>
    </div>
  );
}

function AttachmentsTab({ claim }: { claim: MockClaim }) {
  const attachments = claim.attachments ?? [];
  if (attachments.length === 0) {
    return (
      <div className="text-sm text-ifx-gray-400">
        No attachments uploaded for this claim.
      </div>
    );
  }
  return (
    <ul className="divide-y divide-ifx-gray-100">
      {attachments.map((att) => (
        <li key={att.id} className="flex items-center gap-3 py-2 text-sm">
          <span className="flex-1 font-medium text-ifx-gray-700">{att.name}</span>
          <span className="text-ifx-gray-400">{att.uploaded_at}</span>
        </li>
      ))}
    </ul>
  );
}
