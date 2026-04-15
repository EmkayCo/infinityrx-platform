"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@shared/lib/api-client";
import { ConfigurableDataTable, type Column } from "@/components/ui/configurable-data-table";
import { KpiCardRow } from "@/components/ui/kpi-card-row";
import { FilterPanel, type FilterField, type FilterValues, type PeriodOption } from "@/components/ui/filter-panel";

interface MockClaim {
  id: string;
  fill_date?: string;
  status?: string;
  type?: string;
  pharmacy_name?: string;
  pharmacy_npi?: string;
  rx_number?: string;
  fill_number?: number;
  drug_name?: string;
  drug_ndc?: string;
  member_id?: string;
  patient_name?: string;
  auth_number?: string;
  occ?: string;
  network?: string;
  chain_code?: string;
  statement_account?: string;
  prescriber_id?: string;
  prescriber_name?: string;
  client_name?: string;
  group_id?: string;
  program_name?: string;
  ingredient_cost?: string;
  dispensing_fee?: string;
  copay?: string;
  plan_paid?: string;
  patient_paid?: string;
  total_paid?: string;
  quantity?: string | number;
  days_supply?: number;
  rejection_reason?: string | null;
  rejection_code?: string | null;
  date_of_service?: string;
  sales_tax?: string;
  transaction_fee?: string;
  debit_card_amount?: string;
  pos_adjustment?: string;
  incentive_fee?: string;
  gpi?: string;
  therapeutic_class?: string;
}

interface ClaimsSummary {
  today?: number;
  mtd?: number;
  ytd?: number;
  paid?: number;
  reversals?: number;
  total_billed?: string;
  abandonment_rate?: string;
  avg_benefit?: string;
}

const FILTERS: FilterField[] = [
  { id: "date_from", label: "Date From", type: "date" },
  { id: "date_to", label: "Date To", type: "date" },
  {
    id: "status",
    label: "Status",
    type: "multi-select",
    options: [
      { value: "approved", label: "Paid" },
      { value: "pending", label: "Pending" },
      { value: "rejected", label: "Rejected" },
      { value: "reversed", label: "Reversed" },
      { value: "flagged", label: "Flagged" },
    ],
  },
  {
    id: "client",
    label: "Company Name",
    type: "multi-select",
    options: [
      { value: "acme", label: "Acme Health Partners" },
      { value: "bluestar", label: "BlueStar Benefits Group" },
      { value: "clearpath", label: "ClearPath Managed Care" },
      { value: "delta", label: "Delta Pharmacy Solutions" },
      { value: "emerald", label: "Emerald Coast PBM" },
    ],
  },
  { id: "group_id", label: "Group ID", type: "multi-select", options: [] },
  { id: "ncpdp", label: "NCPDP Provider ID", type: "text", placeholder: "7-digit NCPDP ID" },
  { id: "npi", label: "NPI Number", type: "text", placeholder: "10-digit NPI" },
  {
    id: "occ",
    label: "OCC",
    type: "multi-select",
    options: [
      { value: "00", label: "00 - Not Specified" },
      { value: "01", label: "01 - Carrier" },
      { value: "02", label: "02 - Medicare" },
      { value: "03", label: "03 - Medicaid" },
    ],
  },
  { id: "network", label: "Network ID", type: "multi-select", options: [] },
  { id: "statement_account", label: "Statement Account", type: "multi-select", options: [] },
  { id: "ndc", label: "NDC", type: "text", placeholder: "11-digit NDC" },
  { id: "drug_name", label: "Drug Name", type: "text", placeholder: "Search drug name" },
  { id: "prescriber_id", label: "Prescriber ID", type: "text", placeholder: "Prescriber NPI" },
  {
    id: "chain_code",
    label: "Chain Code",
    type: "multi-select",
    options: [
      { value: "CVS", label: "CVS" },
      { value: "WAG", label: "Walgreens" },
      { value: "RAD", label: "Rite Aid" },
      { value: "WMT", label: "Walmart" },
      { value: "IND", label: "Independent" },
    ],
  },
];

const COLUMNS: Column<MockClaim>[] = [
  {
    id: "fill_date",
    header: "Date",
    accessor: (r) => r.fill_date,
    format: "date",
    pinned: true,
    defaultVisible: true,
  },
  {
    id: "type",
    header: "Type",
    accessor: (r) => r.type ?? "Claim",
    defaultVisible: true,
  },
  {
    id: "status",
    header: "Status",
    accessor: (r) => r.status,
    format: "status",
    defaultVisible: true,
  },
  {
    id: "pharmacy_name",
    header: "Pharmacy Name",
    accessor: (r) => r.pharmacy_name,
    defaultVisible: true,
  },
  {
    id: "pharmacy_npi",
    header: "NPI",
    accessor: (r) => r.pharmacy_npi,
    format: "npi",
    defaultVisible: true,
  },
  {
    id: "rx_number",
    header: "Rx#",
    accessor: (r) => r.rx_number ?? r.id.slice(-8),
    defaultVisible: true,
  },
  {
    id: "fill_number",
    header: "Fill#",
    accessor: (r) => r.fill_number,
    format: "number",
    align: "right",
    defaultVisible: true,
  },
  {
    id: "drug_name",
    header: "Drug Name",
    accessor: (r) => r.drug_name,
    defaultVisible: true,
  },
  {
    id: "drug_ndc",
    header: "NDC",
    accessor: (r) => r.drug_ndc,
    format: "ndc",
    defaultVisible: true,
  },
  {
    id: "patient_name",
    header: "Patient Name",
    accessor: (r) => r.patient_name ?? r.member_id,
    defaultVisible: true,
  },
  {
    id: "auth_number",
    header: "Auth#",
    accessor: (r) => r.auth_number,
    defaultVisible: true,
  },
  {
    id: "occ",
    header: "OCC",
    accessor: (r) => r.occ,
    defaultVisible: true,
  },
  {
    id: "copay",
    header: "Copay Amount",
    accessor: (r) => r.copay,
    format: "currency",
    align: "right",
    defaultVisible: true,
  },
  {
    id: "plan_paid",
    header: "Paid Amount",
    accessor: (r) => r.plan_paid,
    format: "currency",
    align: "right",
    defaultVisible: true,
  },
  // Additional toggleable columns
  {
    id: "member_id",
    header: "Member ID",
    accessor: (r) => r.member_id,
    defaultVisible: false,
  },
  {
    id: "group_id",
    header: "Group ID",
    accessor: (r) => r.group_id,
    defaultVisible: false,
  },
  {
    id: "client_name",
    header: "Client",
    accessor: (r) => r.client_name,
    defaultVisible: false,
  },
  {
    id: "program_name",
    header: "Program",
    accessor: (r) => r.program_name,
    defaultVisible: false,
  },
  {
    id: "prescriber_id",
    header: "Prescriber ID",
    accessor: (r) => r.prescriber_id,
    defaultVisible: false,
  },
  {
    id: "prescriber_name",
    header: "Prescriber Name",
    accessor: (r) => r.prescriber_name,
    defaultVisible: false,
  },
  {
    id: "days_supply",
    header: "Days Supply",
    accessor: (r) => r.days_supply,
    format: "number",
    align: "right",
    defaultVisible: false,
  },
  {
    id: "quantity",
    header: "Quantity",
    accessor: (r) => r.quantity,
    format: "number",
    align: "right",
    defaultVisible: false,
  },
  {
    id: "ingredient_cost",
    header: "Ingredient Cost",
    accessor: (r) => r.ingredient_cost,
    format: "currency",
    align: "right",
    defaultVisible: false,
  },
  {
    id: "dispensing_fee",
    header: "Dispensing Fee",
    accessor: (r) => r.dispensing_fee,
    format: "currency",
    align: "right",
    defaultVisible: false,
  },
  {
    id: "sales_tax",
    header: "Sales Tax",
    accessor: (r) => r.sales_tax,
    format: "currency",
    align: "right",
    defaultVisible: false,
  },
  {
    id: "patient_paid",
    header: "Patient Paid",
    accessor: (r) => r.patient_paid,
    format: "currency",
    align: "right",
    defaultVisible: false,
  },
  {
    id: "transaction_fee",
    header: "Transaction Fee",
    accessor: (r) => r.transaction_fee,
    format: "currency",
    align: "right",
    defaultVisible: false,
  },
  {
    id: "debit_card_amount",
    header: "Debit Card Amount",
    accessor: (r) => r.debit_card_amount,
    format: "currency",
    align: "right",
    defaultVisible: false,
  },
  {
    id: "pos_adjustment",
    header: "POS Adjustment",
    accessor: (r) => r.pos_adjustment,
    format: "currency",
    align: "right",
    defaultVisible: false,
  },
  {
    id: "incentive_fee",
    header: "Incentive Fee",
    accessor: (r) => r.incentive_fee,
    format: "currency",
    align: "right",
    defaultVisible: false,
  },
  {
    id: "chain_code",
    header: "Chain Code",
    accessor: (r) => r.chain_code,
    defaultVisible: false,
  },
  {
    id: "network",
    header: "Network",
    accessor: (r) => r.network,
    defaultVisible: false,
  },
  {
    id: "statement_account",
    header: "Statement Account",
    accessor: (r) => r.statement_account,
    defaultVisible: false,
  },
  {
    id: "gpi",
    header: "GPI",
    accessor: (r) => r.gpi,
    defaultVisible: false,
  },
  {
    id: "therapeutic_class",
    header: "Therapeutic Class",
    accessor: (r) => r.therapeutic_class,
    defaultVisible: false,
  },
  {
    id: "rejection_code",
    header: "Reject Code",
    accessor: (r) => r.rejection_code,
    defaultVisible: false,
  },
  {
    id: "rejection_reason",
    header: "Reject Reason",
    accessor: (r) => r.rejection_reason,
    defaultVisible: false,
  },
];

export default function ClaimsExplorerPage() {
  const router = useRouter();
  const [filterValues, setFilterValues] = useState<FilterValues>({});
  const [period, setPeriod] = useState<PeriodOption>("monthly");

  const { data: summary } = useQuery<ClaimsSummary>({
    queryKey: ["claims-summary"],
    queryFn: () => apiGet<ClaimsSummary>("/billing/v1/claims/summary"),
  });

  const { data, isLoading } = useQuery<{ items: MockClaim[]; total: number }>({
    queryKey: ["claims-list"],
    queryFn: () => apiGet<{ items: MockClaim[]; total: number }>("/billing/v1/claims"),
  });

  const rows = data?.items ?? [];

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <span className="text-[11px] font-semibold uppercase tracking-wider text-ifx-navy">
            Claims
          </span>
          <h1 className="mt-1 text-2xl font-bold text-ifx-gray-900">Claims Explorer</h1>
          <p className="mt-1 text-sm text-ifx-gray-400">
            Browse, filter, and investigate every pharmacy claim processed on InfinityRx.
          </p>
        </div>
        <nav
          aria-label="Claims sub-navigation"
          className="flex gap-1 rounded-lg border border-ifx-gray-100 bg-white p-1"
        >
          {(
            [
              { href: "/claims", label: "Explorer" },
              { href: "/claims/lookup", label: "Lookup" },
              { href: "/claims/manual", label: "Manual Claims" },
              { href: "/claims/pa-override", label: "PA Override" },
            ] as const
          ).map(({ href, label }) => (
            <a
              key={href}
              href={href}
              className="rounded px-3 py-1.5 text-xs font-medium text-ifx-gray-700 hover:bg-ifx-gray-50 transition-colors aria-[current=page]:bg-ifx-navy aria-[current=page]:text-white"
              aria-current={href === "/claims" ? "page" : undefined}
            >
              {label}
            </a>
          ))}
        </nav>
      </header>

      <KpiCardRow
        cards={[
          {
            label: "Total Claims (YTD)",
            value: summary?.ytd ?? rows.length,
            format: "number",
            accentColor: "var(--ifx-navy)",
            href: "/claims",
          },
          {
            label: "Net Claims",
            value: summary?.paid ?? rows.filter((r) => r.status === "approved").length,
            format: "number",
            accentColor: "var(--ifx-blue)",
          },
          {
            label: "Total Benefit Spend",
            value: summary?.total_billed ?? "0",
            format: "currency-compact",
            accentColor: "var(--ifx-success)",
          },
          {
            label: "Avg Benefit",
            value: summary?.avg_benefit ?? "0",
            format: "currency",
            accentColor: "var(--ifx-blue)",
          },
          {
            label: "Reversals",
            value: summary?.reversals ?? rows.filter((r) => r.status === "reversed").length,
            format: "number",
            accentColor: "var(--ifx-error)",
          },
          {
            label: "Abandonment Rate",
            value: summary?.abandonment_rate ?? "0",
            format: "percent",
            accentColor: "var(--ifx-warning)",
          },
        ]}
      />

      <div className="flex gap-4">
        <FilterPanel
          filters={FILTERS}
          values={filterValues}
          onChange={setFilterValues}
          onClear={() => setFilterValues({})}
          periodToggle
          period={period}
          onPeriodChange={setPeriod}
          collapsible
        />

        <div className="min-w-0 flex-1">
          <ConfigurableDataTable
            tableId="claims-explorer"
            columns={COLUMNS}
            data={rows}
            getRowId={(r) => r.id}
            onRowClick={(row) => router.push(`/claims/${row.id}`)}
            loading={isLoading}
            emptyMessage="No claims match the current filters."
            pagination={{ pageSize: 25, pageSizeOptions: [25, 50, 100] }}
          />
        </div>
      </div>
    </div>
  );
}
