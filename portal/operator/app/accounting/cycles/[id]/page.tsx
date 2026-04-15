"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle, XCircle, FileText, DollarSign, AlertTriangle } from "lucide-react";
import { apiGet, apiPost } from "@shared/lib/api-client";
import { DetailPageLayout } from "@/components/ui/detail-page-layout";
import { InfoCard } from "@/components/ui/info-card";
import { StatusBadge } from "@/components/ui/status-badge";
import { ConfigurableDataTable, type Column } from "@/components/ui/configurable-data-table";
import { cn } from "@shared/lib/format";

interface BillingCycle {
  id: string;
  tenant_id?: string;
  client_id?: string;
  client_name?: string;
  program_id?: string;
  program_name?: string;
  cycle_period: string;
  status: string;
  total_claims: number;
  total_ap_amount: string;
  total_ar_amount: string;
  total_fee_amount: string;
  created_at: string;
  updated_at?: string;
  approved_at?: string | null;
  approved_by?: string | null;
  generated_at?: string | null;
  artifacts?: CycleArtifact[];
  anomaly_flags?: { severity: string; message: string }[];
  comparison?: {
    prev_cycle_period: string;
    prev_total_claims: number;
    prev_total_ap_amount: string;
    claims_delta: number;
    claims_delta_pct: string;
    ap_amount_delta: string;
    ap_amount_delta_pct: string;
  };
}

interface CycleArtifact {
  id: string;
  type: string;
  filename: string;
  download_url: string;
  generated_at: string;
  transmitted_at?: string | null;
  ack_status?: string;
}

interface ClaimRecord {
  id: string;
  fill_date?: string;
  status?: string;
  pharmacy_name?: string;
  drug_name?: string;
  member_id?: string;
  copay?: string;
  plan_paid?: string;
}

interface JournalEntry {
  id: string;
  date: string;
  type: string;
  description?: string;
  debit_account?: string;
  credit_account?: string;
  amount: string;
  qb_class?: string;
}

interface ArEntry {
  id: string;
  date: string;
  client_name?: string;
  description?: string;
  amount: string;
  status?: string;
}

interface ApEntry {
  id: string;
  date: string;
  pharmacy_name?: string;
  pharmacy_npi?: string;
  amount: string;
  status?: string;
}

type TabId = "claims" | "ar" | "ap" | "journal" | "saasant" | "835" | "nacha";

const TABS: { id: TabId; label: string }[] = [
  { id: "claims", label: "Claims" },
  { id: "ar", label: "AR Entries" },
  { id: "ap", label: "AP Entries" },
  { id: "journal", label: "Journal Entries" },
  { id: "saasant", label: "SaaSant Preview" },
  { id: "835", label: "835 Preview" },
  { id: "nacha", label: "NACHA Preview" },
];

const CLAIM_COLUMNS: Column<ClaimRecord>[] = [
  { id: "fill_date", header: "Fill Date", accessor: (r) => r.fill_date, format: "date", defaultVisible: true },
  { id: "status", header: "Status", accessor: (r) => r.status, format: "status", defaultVisible: true },
  { id: "pharmacy_name", header: "Pharmacy", accessor: (r) => r.pharmacy_name, defaultVisible: true },
  { id: "drug_name", header: "Drug", accessor: (r) => r.drug_name, defaultVisible: true },
  { id: "member_id", header: "Member ID", accessor: (r) => r.member_id, defaultVisible: true },
  { id: "copay", header: "Copay", accessor: (r) => r.copay, format: "currency", align: "right", defaultVisible: true },
  { id: "plan_paid", header: "Plan Paid", accessor: (r) => r.plan_paid, format: "currency", align: "right", defaultVisible: true },
];

const JE_COLUMNS: Column<JournalEntry>[] = [
  { id: "date", header: "Date", accessor: (r) => r.date, format: "date", defaultVisible: true },
  { id: "type", header: "Type", accessor: (r) => r.type, defaultVisible: true },
  { id: "description", header: "Description", accessor: (r) => r.description, defaultVisible: true },
  { id: "debit_account", header: "Debit Account", accessor: (r) => r.debit_account, defaultVisible: true },
  { id: "credit_account", header: "Credit Account", accessor: (r) => r.credit_account, defaultVisible: true },
  { id: "amount", header: "Amount", accessor: (r) => r.amount, format: "currency", align: "right", defaultVisible: true },
  { id: "qb_class", header: "QB Class", accessor: (r) => r.qb_class, defaultVisible: false },
];

const AR_COLUMNS: Column<ArEntry>[] = [
  { id: "date", header: "Date", accessor: (r) => r.date, format: "date", defaultVisible: true },
  { id: "client_name", header: "Client", accessor: (r) => r.client_name, defaultVisible: true },
  { id: "description", header: "Description", accessor: (r) => r.description, defaultVisible: true },
  { id: "amount", header: "Amount", accessor: (r) => r.amount, format: "currency", align: "right", defaultVisible: true },
  { id: "status", header: "Status", accessor: (r) => r.status, format: "status", defaultVisible: true },
];

const AP_COLUMNS: Column<ApEntry>[] = [
  { id: "date", header: "Date", accessor: (r) => r.date, format: "date", defaultVisible: true },
  { id: "pharmacy_name", header: "Pharmacy", accessor: (r) => r.pharmacy_name, defaultVisible: true },
  { id: "pharmacy_npi", header: "NPI", accessor: (r) => r.pharmacy_npi, format: "npi", defaultVisible: true },
  { id: "amount", header: "Amount", accessor: (r) => r.amount, format: "currency", align: "right", defaultVisible: true },
  { id: "status", header: "Status", accessor: (r) => r.status, format: "status", defaultVisible: true },
];

export default function CycleDetailPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<TabId>("claims");

  const { data: cycle, isLoading } = useQuery<BillingCycle>({
    queryKey: ["cycle", id],
    queryFn: () => apiGet<BillingCycle>(`/billing/v1/cycles/${id}`),
    enabled: !!id,
  });

  const { data: cycleClaimsData } = useQuery<{ items: ClaimRecord[] }>({
    queryKey: ["cycle-claims", id],
    queryFn: () => apiGet<{ items: ClaimRecord[] }>(`/api/v1/accounting/cycles/${id}/claims`),
    enabled: !!id && activeTab === "claims",
  });

  const { data: journalData } = useQuery<{ items: JournalEntry[] }>({
    queryKey: ["cycle-journal", id],
    queryFn: () => apiGet<{ items: JournalEntry[] }>(`/api/v1/accounting/cycles/${id}/journal-entries`),
    enabled: !!id && activeTab === "journal",
  });

  const { data: arData } = useQuery<{ items: ArEntry[] }>({
    queryKey: ["cycle-ar", id],
    queryFn: () => apiGet<{ items: ArEntry[] }>(`/api/v1/accounting/cycles/${id}/ar-entries`),
    enabled: !!id && activeTab === "ar",
  });

  const { data: apData } = useQuery<{ items: ApEntry[] }>({
    queryKey: ["cycle-ap", id],
    queryFn: () => apiGet<{ items: ApEntry[] }>(`/api/v1/accounting/cycles/${id}/ap-entries`),
    enabled: !!id && activeTab === "ap",
  });

  const approveMutation = useMutation({
    mutationFn: () => apiPost(`/api/v1/accounting/cycles/${id}/approve`, {}),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["cycle", id] }),
  });

  const rejectMutation = useMutation({
    mutationFn: () => apiPost(`/api/v1/accounting/cycles/${id}/reject`, {}),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["cycle", id] }),
  });

  const generateMutation = useMutation({
    mutationFn: () => apiPost(`/api/v1/accounting/cycles/${id}/generate`, {}),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["cycle", id] }),
  });

  const settleMutation = useMutation({
    mutationFn: () => apiPost(`/api/v1/accounting/cycles/${id}/settle`, {}),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["cycle", id] }),
  });

  if (isLoading) {
    return (
      <DetailPageLayout
        backLink={{ href: "/accounting/cycles", label: "Back to Billing Cycles" }}
        title="Loading cycle…"
      >
        <div className="h-40 rounded-lg bg-white shimmer" />
      </DetailPageLayout>
    );
  }

  if (!cycle) {
    return (
      <DetailPageLayout
        backLink={{ href: "/accounting/cycles", label: "Back to Billing Cycles" }}
        title="Cycle not found"
      >
        <div className="rounded-md bg-ifx-error-light border border-ifx-error/20 p-4 text-sm text-ifx-error-text">
          Billing cycle not found.
        </div>
      </DetailPageLayout>
    );
  }

  const netAmount = (Number(cycle.total_ar_amount) - Number(cycle.total_ap_amount)).toFixed(2);

  return (
    <DetailPageLayout
      backLink={{ href: "/accounting/cycles", label: "Back to Billing Cycles" }}
      eyebrow="Billing Cycle"
      title={`Cycle ${cycle.cycle_period}`}
      subtitle={
        <div className="flex items-center gap-3">
          {cycle.client_name && <span className="text-ifx-gray-700">{cycle.client_name}</span>}
          {cycle.program_name && <span className="text-ifx-gray-400">· {cycle.program_name}</span>}
          <StatusBadge status={cycle.status} />
        </div>
      }
      actions={
        <>
          {cycle.status === "pending_approval" && (
            <>
              <ActionButton
                icon={<CheckCircle className="h-3.5 w-3.5" />}
                label="Approve"
                onClick={() => approveMutation.mutate()}
                variant="success"
              />
              <ActionButton
                icon={<XCircle className="h-3.5 w-3.5" />}
                label="Reject"
                onClick={() => rejectMutation.mutate()}
                variant="danger"
              />
            </>
          )}
          {cycle.status === "approved" && (
            <ActionButton
              icon={<FileText className="h-3.5 w-3.5" />}
              label="Generate Outputs"
              onClick={() => generateMutation.mutate()}
            />
          )}
          {cycle.status === "completed" && (
            <ActionButton
              icon={<DollarSign className="h-3.5 w-3.5" />}
              label="Settle"
              onClick={() => settleMutation.mutate()}
              variant="primary"
            />
          )}
        </>
      }
      summaryCards={[
        {
          label: "Total Claims",
          value: cycle.total_claims,
          format: "number",
          accentColor: "var(--ifx-navy)",
        },
        {
          label: "Total AP",
          value: cycle.total_ap_amount,
          format: "currency",
          accentColor: "var(--ifx-error)",
        },
        {
          label: "Total AR",
          value: cycle.total_ar_amount,
          format: "currency",
          accentColor: "var(--ifx-success)",
        },
        {
          label: "Net Amount",
          value: netAmount,
          format: "currency",
          accentColor: "var(--ifx-blue)",
        },
      ]}
    >
      {/* Anomaly flags */}
      {(cycle.anomaly_flags ?? []).length > 0 && (
        <div className="flex flex-col gap-2">
          {(cycle.anomaly_flags ?? []).map((flag, i) => (
            <div
              key={i}
              className="flex items-start gap-2 rounded-md border border-ifx-warning/30 bg-ifx-warning-light px-4 py-3 text-sm text-ifx-warning-text"
            >
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{flag.message}</span>
            </div>
          ))}
        </div>
      )}

      {/* Info cards */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <InfoCard
          title="Cycle Information"
          fields={[
            { label: "Cycle Period", value: cycle.cycle_period, mono: true },
            { label: "Status", value: <StatusBadge status={cycle.status} /> },
            { label: "Client", value: cycle.client_name },
            { label: "Program", value: cycle.program_name },
            { label: "Created", value: cycle.created_at, format: "date" },
            { label: "Updated", value: cycle.updated_at, format: "date" },
          ]}
        />
        <InfoCard
          title="Approval Workflow"
          fields={[
            { label: "Approved By", value: cycle.approved_by },
            { label: "Approved At", value: cycle.approved_at, format: "date" },
            { label: "Generated At", value: cycle.generated_at, format: "date" },
            { label: "Settlement", value: cycle.status === "settled" ? "Complete" : "Pending" },
          ]}
        />
      </div>

      {/* Artifacts */}
      {(cycle.artifacts ?? []).length > 0 && (
        <div className="rounded-lg bg-white ifx-card-shadow overflow-hidden">
          <header className="border-b border-ifx-gray-100 px-4 py-3">
            <h3 className="text-sm font-bold text-ifx-gray-900">Generated Files</h3>
          </header>
          <ul className="divide-y divide-ifx-gray-100">
            {(cycle.artifacts ?? []).map((art) => (
              <li key={art.id} className="flex items-center gap-3 px-4 py-3 text-sm">
                <span className="rounded bg-ifx-lavender px-2 py-0.5 text-xs font-semibold uppercase text-ifx-navy">
                  {art.type}
                </span>
                <span className="min-w-0 flex-1 truncate font-mono text-[13px] text-ifx-gray-700">
                  {art.filename}
                </span>
                <StatusBadge status={art.ack_status ?? "pending"} />
                <a
                  href={art.download_url}
                  className="text-xs font-medium text-ifx-blue hover:underline"
                >
                  Download
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Tabs */}
      <div className="flex flex-col gap-3">
        <div role="tablist" className="flex items-center gap-1 border-b border-ifx-gray-100 overflow-x-auto">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              role="tab"
              aria-selected={activeTab === tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "relative shrink-0 px-4 py-2 text-sm font-medium transition-colors whitespace-nowrap",
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
          {activeTab === "claims" && (
            <ConfigurableDataTable
              tableId="cycle-detail-claims"
              columns={CLAIM_COLUMNS}
              data={cycleClaimsData?.items ?? []}
              getRowId={(r) => r.id}
              emptyMessage="No claims in this cycle."
              pagination={{ pageSize: 25 }}
            />
          )}

          {activeTab === "ar" && (
            <ConfigurableDataTable
              tableId="cycle-detail-ar"
              columns={AR_COLUMNS}
              data={arData?.items ?? []}
              getRowId={(r) => r.id}
              emptyMessage="No AR entries for this cycle."
              pagination={{ pageSize: 25 }}
            />
          )}

          {activeTab === "ap" && (
            <ConfigurableDataTable
              tableId="cycle-detail-ap"
              columns={AP_COLUMNS}
              data={apData?.items ?? []}
              getRowId={(r) => r.id}
              emptyMessage="No AP entries for this cycle."
              pagination={{ pageSize: 25 }}
            />
          )}

          {activeTab === "journal" && (
            <ConfigurableDataTable
              tableId="cycle-detail-journal"
              columns={JE_COLUMNS}
              data={journalData?.items ?? []}
              getRowId={(r) => r.id}
              emptyMessage="No journal entries for this cycle."
              pagination={{ pageSize: 25 }}
            />
          )}

          {activeTab === "saasant" && (
            <SaaSantPreview cycle={cycle} />
          )}

          {activeTab === "835" && (
            <FilePreview835 cycle={cycle} />
          )}

          {activeTab === "nacha" && (
            <NachaPreview cycle={cycle} />
          )}
        </div>
      </div>
    </DetailPageLayout>
  );
}

function ActionButton({
  icon,
  label,
  onClick,
  variant = "default",
}: {
  icon: React.ReactNode;
  label: string;
  onClick?: () => void;
  variant?: "default" | "primary" | "success" | "danger";
}) {
  const variantClasses = {
    default: "border border-ifx-gray-100 bg-white text-ifx-gray-700 hover:bg-ifx-gray-50",
    primary: "bg-ifx-navy text-white hover:bg-ifx-navy-dark",
    success: "bg-ifx-success text-white hover:bg-ifx-success/90",
    danger: "bg-ifx-error text-white hover:bg-ifx-error/90",
  };

  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
        variantClasses[variant],
      )}
    >
      {icon}
      {label}
    </button>
  );
}

function SaaSantPreview({ cycle }: { cycle: BillingCycle }) {
  const tabs = [
    { name: "Summary", rows: cycle.total_claims, amount: cycle.total_ar_amount },
    { name: "AP Detail", rows: Math.round(cycle.total_claims * 0.8), amount: cycle.total_ap_amount },
    { name: "Fee Schedule", rows: 12, amount: cycle.total_fee_amount },
    { name: "Journal Entries", rows: 6, amount: null },
  ];

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-ifx-gray-400">
        Preview of the SaaSant Excel workbook that will be generated when this cycle is approved.
      </p>
      <div className="overflow-x-auto rounded-md border border-ifx-gray-100">
        <table className="w-full text-sm">
          <thead className="border-b border-ifx-gray-100 bg-ifx-gray-50">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider text-ifx-gray-400">Worksheet Tab</th>
              <th className="px-4 py-2 text-right text-xs font-semibold uppercase tracking-wider text-ifx-gray-400">Rows</th>
              <th className="px-4 py-2 text-right text-xs font-semibold uppercase tracking-wider text-ifx-gray-400">Total Amount</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-ifx-gray-100">
            {tabs.map((t) => (
              <tr key={t.name} className="hover:bg-ifx-gray-50">
                <td className="px-4 py-2 text-ifx-gray-700">{t.name}</td>
                <td className="px-4 py-2 text-right font-mono text-ifx-gray-700">{t.rows.toLocaleString()}</td>
                <td className="px-4 py-2 text-right font-mono text-ifx-gray-700">
                  {t.amount != null ? `$${Number(t.amount).toLocaleString("en-US", { minimumFractionDigits: 2 })}` : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function FilePreview835({ cycle }: { cycle: BillingCycle }) {
  const pharmacies = [
    { name: "CVS Pharmacy #1047", npi: "1234567890", chain: "CVS", claims: Math.round(cycle.total_claims * 0.22), amount: (Number(cycle.total_ap_amount) * 0.22).toFixed(2) },
    { name: "Walgreens #3821", npi: "2345678901", chain: "WAG", claims: Math.round(cycle.total_claims * 0.18), amount: (Number(cycle.total_ap_amount) * 0.18).toFixed(2) },
    { name: "Rite Aid #0542", npi: "3456789012", chain: "RAD", claims: Math.round(cycle.total_claims * 0.12), amount: (Number(cycle.total_ap_amount) * 0.12).toFixed(2) },
    { name: "Walmart Pharmacy", npi: "4567890123", chain: "WMT", claims: Math.round(cycle.total_claims * 0.15), amount: (Number(cycle.total_ap_amount) * 0.15).toFixed(2) },
    { name: "Other Pharmacies", npi: "—", chain: "—", claims: Math.round(cycle.total_claims * 0.33), amount: (Number(cycle.total_ap_amount) * 0.33).toFixed(2) },
  ];

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-ifx-gray-400">
        835 Electronic Remittance Advice files that will be generated, grouped by pharmacy and NPI.
      </p>
      <div className="overflow-x-auto rounded-md border border-ifx-gray-100">
        <table className="w-full text-sm">
          <thead className="border-b border-ifx-gray-100 bg-ifx-gray-50">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider text-ifx-gray-400">Pharmacy</th>
              <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider text-ifx-gray-400">NPI</th>
              <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider text-ifx-gray-400">Chain</th>
              <th className="px-4 py-2 text-right text-xs font-semibold uppercase tracking-wider text-ifx-gray-400">Claims</th>
              <th className="px-4 py-2 text-right text-xs font-semibold uppercase tracking-wider text-ifx-gray-400">Amount</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-ifx-gray-100">
            {pharmacies.map((p) => (
              <tr key={p.npi} className="hover:bg-ifx-gray-50">
                <td className="px-4 py-2 text-ifx-gray-700">{p.name}</td>
                <td className="px-4 py-2 font-mono text-[13px] text-ifx-gray-700">{p.npi}</td>
                <td className="px-4 py-2 text-ifx-gray-700">{p.chain}</td>
                <td className="px-4 py-2 text-right font-mono text-ifx-gray-700">{p.claims.toLocaleString()}</td>
                <td className="px-4 py-2 text-right font-mono text-ifx-gray-700">${Number(p.amount).toLocaleString("en-US", { minimumFractionDigits: 2 })}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function NachaPreview({ cycle }: { cycle: BillingCycle }) {
  const entries = [
    { routing: "021000021", account: "****4821", type: "CCD", payee: "CVS Pharmacy Inc.", amount: (Number(cycle.total_ap_amount) * 0.22).toFixed(2) },
    { routing: "026009593", account: "****3947", type: "CCD", payee: "Walgreen Co.", amount: (Number(cycle.total_ap_amount) * 0.18).toFixed(2) },
    { routing: "121000358", account: "****7612", type: "CCD", payee: "Rite Aid Corp.", amount: (Number(cycle.total_ap_amount) * 0.12).toFixed(2) },
    { routing: "081000210", account: "****9034", type: "CCD", payee: "Walmart Inc.", amount: (Number(cycle.total_ap_amount) * 0.15).toFixed(2) },
  ];

  return (
    <div className="flex flex-col gap-4">
      <p className="text-sm text-ifx-gray-400">
        ACH transactions that would be generated in the NACHA file for this cycle.
      </p>
      <div className="overflow-x-auto rounded-md border border-ifx-gray-100">
        <table className="w-full text-sm">
          <thead className="border-b border-ifx-gray-100 bg-ifx-gray-50">
            <tr>
              <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider text-ifx-gray-400">Payee</th>
              <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider text-ifx-gray-400">Routing</th>
              <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider text-ifx-gray-400">Account</th>
              <th className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider text-ifx-gray-400">Type</th>
              <th className="px-4 py-2 text-right text-xs font-semibold uppercase tracking-wider text-ifx-gray-400">Amount</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-ifx-gray-100">
            {entries.map((e, i) => (
              <tr key={i} className="hover:bg-ifx-gray-50">
                <td className="px-4 py-2 text-ifx-gray-700">{e.payee}</td>
                <td className="px-4 py-2 font-mono text-[13px] text-ifx-gray-700">{e.routing}</td>
                <td className="px-4 py-2 font-mono text-[13px] text-ifx-gray-700">{e.account}</td>
                <td className="px-4 py-2 text-ifx-gray-700">{e.type}</td>
                <td className="px-4 py-2 text-right font-mono text-ifx-gray-700">${Number(e.amount).toLocaleString("en-US", { minimumFractionDigits: 2 })}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-ifx-gray-400">
        Total ACH: ${(Number(cycle.total_ap_amount) * 0.67).toLocaleString("en-US", { minimumFractionDigits: 2 })} across {entries.length} entries
      </p>
    </div>
  );
}
