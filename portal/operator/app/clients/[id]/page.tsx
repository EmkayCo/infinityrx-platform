"use client";

import { use, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Pencil, Save } from "lucide-react";
import { DetailPageLayout } from "@/components/ui/detail-page-layout";
import { InfoCard } from "@/components/ui/info-card";
import { ConfigurableDataTable, type Column } from "@/components/ui/configurable-data-table";
import { StatusBadge } from "@/components/ui/status-badge";
import { cn } from "@shared/lib/format";
import { apiGet, apiPatch } from "@shared/lib/api-client";
import type { ClientRow, ClientFeeConfig, StatementProviderRow, BlockedProviderRow } from "@shared/lib/mock-data/seed/programs";

// ─── Tabs ─────────────────────────────────────────────────────────────────────

const TABS = [
  { id: "details", label: "Client Details" },
  { id: "profile", label: "Client Profile" },
  { id: "programs", label: "Client Programs" },
  { id: "statement_providers", label: "Statement Providers" },
  { id: "blocked_providers", label: "Blocked Providers" },
] as const;
type TabId = (typeof TABS)[number]["id"];

// ─── Client Details tab ───────────────────────────────────────────────────────

function ClientDetailsTab({ client, clientId }: { client: ClientRow; clientId: string }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({
    company_name: client.company_name,
    address_line1: client.address_line1,
    address_line2: client.address_line2 ?? "",
    city: client.city,
    state: client.state,
    zip: client.zip,
    phone: client.phone,
    email: client.email,
    contact_name: client.contact_name,
    federal_id: client.federal_id,
    bin: client.bin,
  });
  const [saved, setSaved] = useState(false);

  const mutation = useMutation({
    mutationFn: (data: typeof form) => apiPatch(`/api/v1/clients/${clientId}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["client", clientId] });
      setEditing(false);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    },
  });

  if (!editing) {
    return (
      <div className="space-y-4">
        <InfoCard
          title="Company Information"
          columns={2}
          fields={[
            { label: "Company Name", value: client.company_name, span: 2 },
            { label: "Federal ID", value: client.federal_id, mono: true },
            { label: "BIN", value: client.bin, mono: true },
            { label: "Status", value: <StatusBadge status={client.status} variant={client.status === "enabled" ? "success" : "neutral"} /> },
          ]}
          actions={
            <button
              onClick={() => setEditing(true)}
              className="inline-flex items-center gap-1.5 text-xs font-medium text-ifx-blue hover:text-ifx-navy"
            >
              <Pencil className="h-3.5 w-3.5" /> Edit
            </button>
          }
        />
        <InfoCard
          title="Contact Information"
          columns={2}
          fields={[
            { label: "Contact Name", value: client.contact_name },
            { label: "Email", value: client.email },
            { label: "Phone", value: client.phone },
            { label: "Address", value: `${client.address_line1}${client.address_line2 ? `, ${client.address_line2}` : ""}`, span: 2 },
            { label: "City", value: client.city },
            { label: "State / ZIP", value: `${client.state} ${client.zip}` },
          ]}
        />
        {saved && <p className="text-sm text-green-600">Changes saved.</p>}
      </div>
    );
  }

  return (
    <form
      onSubmit={(e) => { e.preventDefault(); mutation.mutate(form); }}
      className="space-y-4"
    >
      <div className="rounded-lg bg-white ifx-card-shadow p-4">
        <h4 className="text-sm font-bold text-ifx-gray-900 mb-4">Edit Client Details</h4>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {[
            { name: "company_name" as const, label: "Company Name", type: "text", span: 2 },
            { name: "federal_id" as const, label: "Federal ID", type: "text" },
            { name: "bin" as const, label: "BIN", type: "text" },
            { name: "contact_name" as const, label: "Contact Name", type: "text" },
            { name: "email" as const, label: "Email", type: "email" },
            { name: "phone" as const, label: "Phone", type: "tel" },
            { name: "address_line1" as const, label: "Address Line 1", type: "text" },
            { name: "address_line2" as const, label: "Address Line 2", type: "text" },
            { name: "city" as const, label: "City", type: "text" },
            { name: "state" as const, label: "State", type: "text" },
            { name: "zip" as const, label: "ZIP", type: "text" },
          ].map((field) => (
            <div
              key={field.name}
              className={cn("flex flex-col gap-1", field.span === 2 && "sm:col-span-2")}
            >
              <label className="text-[10px] font-semibold uppercase tracking-wider text-ifx-gray-400">
                {field.label}
              </label>
              <input
                type={field.type}
                value={form[field.name]}
                onChange={(e) => setForm((prev) => ({ ...prev, [field.name]: e.target.value }))}
                className="rounded border border-ifx-gray-100 px-3 py-2 text-sm text-ifx-gray-900 focus:border-ifx-blue focus:outline-none"
              />
            </div>
          ))}
        </div>
      </div>
      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={mutation.isPending}
          className="inline-flex items-center gap-2 rounded-md bg-[var(--ifx-navy)] px-5 py-2 text-sm font-semibold text-white hover:bg-[var(--ifx-navy-dark)] disabled:opacity-50 transition-colors"
        >
          <Save className="h-4 w-4" />
          {mutation.isPending ? "Saving…" : "Save"}
        </button>
        <button
          type="button"
          onClick={() => setEditing(false)}
          className="rounded-md border border-ifx-gray-100 px-5 py-2 text-sm font-medium text-ifx-gray-700 hover:border-ifx-blue transition-colors"
        >
          Cancel
        </button>
        {mutation.isError && (
          <span className="text-sm text-red-500">Save failed — please try again.</span>
        )}
      </div>
    </form>
  );
}

// ─── Client Profile tab (fee configuration) ───────────────────────────────────

function ClientProfileTab({ clientId }: { clientId: string }) {
  const queryClient = useQueryClient();
  const { data: fees, isLoading } = useQuery({
    queryKey: ["client-fees", clientId],
    queryFn: () => apiGet<ClientFeeConfig>(`/api/v1/clients/${clientId}/fees`),
  });

  const [form, setForm] = useState<Partial<ClientFeeConfig>>({});
  const [editing, setEditing] = useState(false);
  const [saved, setSaved] = useState(false);

  const mutation = useMutation({
    mutationFn: (data: Partial<ClientFeeConfig>) =>
      apiPatch<ClientFeeConfig>(`/api/v1/clients/${clientId}/fees`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["client-fees", clientId] });
      setEditing(false);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    },
  });

  if (isLoading) return <div className="h-40 shimmer rounded" />;
  if (!fees) return <p className="text-sm text-ifx-gray-400">No fee configuration found.</p>;

  const currentFees = { ...fees, ...form };

  const feeFields: { key: keyof ClientFeeConfig; label: string }[] = [
    { key: "ibl_setup_fee", label: "IBL Setup Fee" },
    { key: "icp_setup_fee", label: "ICP Setup Fee" },
    { key: "pharmacy_trans_fee", label: "Pharmacy Trans Fee" },
    { key: "claim_processing_fee", label: "Claim Processing Fee" },
    { key: "pharmacy_disp_fee", label: "Pharmacy Disp Fee" },
    { key: "minimum_balance", label: "Minimum Balance" },
    { key: "opening_balance", label: "Opening Balance" },
    { key: "icp_service_fee_monthly", label: "ICP Service Fee (Monthly)" },
    { key: "ibl_service_fee_monthly", label: "IBL Service Fee (Monthly)" },
  ];

  if (!editing) {
    return (
      <div className="space-y-4">
        <InfoCard
          title="Account Setup Fees"
          columns={2}
          fields={feeFields.map(({ key, label }) => ({
            label,
            value: fees[key] as string,
            format: "currency" as const,
          }))}
          actions={
            <button
              onClick={() => { setForm({}); setEditing(true); }}
              className="inline-flex items-center gap-1.5 text-xs font-medium text-ifx-blue hover:text-ifx-navy"
            >
              <Pencil className="h-3.5 w-3.5" /> Edit Fees
            </button>
          }
        />
        <InfoCard
          title="Service Fee Schedule"
          columns={2}
          fields={[
            { label: "IBL Service Fee Start", value: fees.ibl_service_fee_start, format: "date" as const },
            { label: "IBL Service Fee End", value: fees.ibl_service_fee_end ?? "Active (no end date)" },
          ]}
        />
        {saved && <p className="text-sm text-green-600">Fees saved successfully.</p>}
      </div>
    );
  }

  return (
    <form
      onSubmit={(e) => { e.preventDefault(); mutation.mutate(form); }}
      className="space-y-4"
    >
      <div className="rounded-lg bg-white ifx-card-shadow p-4">
        <h4 className="text-sm font-bold text-ifx-gray-900 mb-4">Edit Fee Configuration</h4>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {feeFields.map(({ key, label }) => (
            <div key={String(key)} className="flex flex-col gap-1">
              <label className="text-[10px] font-semibold uppercase tracking-wider text-ifx-gray-400">
                {label}
              </label>
              <input
                type="text"
                data-fee-field={String(key)}
                pattern="^\d+(\.\d{1,4})?$"
                defaultValue={String(currentFees[key] ?? "")}
                onChange={(e) => setForm((prev) => ({ ...prev, [key]: e.target.value }))}
                className="rounded border border-ifx-gray-100 px-3 py-2 text-sm text-ifx-gray-900 focus:border-ifx-blue focus:outline-none"
              />
            </div>
          ))}
        </div>
      </div>
      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={mutation.isPending}
          className="inline-flex items-center gap-2 rounded-md bg-[var(--ifx-navy)] px-5 py-2 text-sm font-semibold text-white hover:bg-[var(--ifx-navy-dark)] disabled:opacity-50 transition-colors"
        >
          <Save className="h-4 w-4" />
          {mutation.isPending ? "Saving…" : "Save Fees"}
        </button>
        <button
          type="button"
          onClick={() => setEditing(false)}
          className="rounded-md border border-ifx-gray-100 px-5 py-2 text-sm font-medium text-ifx-gray-700 hover:border-ifx-blue transition-colors"
        >
          Cancel
        </button>
        {mutation.isError && (
          <span className="text-sm text-red-500">Save failed — please try again.</span>
        )}
      </div>
    </form>
  );
}

// ─── Client Programs tab ──────────────────────────────────────────────────────

interface ProgramSummary {
  id: string;
  name: string;
  status: string;
  active_enrollments: number;
  total_spend_ytd: string;
  gtn_ratio: string;
}

const PROG_COLS: Column<ProgramSummary>[] = [
  { id: "name", header: "Program Name", accessor: (r) => r.name, defaultVisible: true, pinned: true },
  { id: "status", header: "Status", accessor: (r) => r.status, defaultVisible: true, cell: (v) => <StatusBadge status={String(v)} variant={v === "active" ? "success" : "warning"} /> },
  { id: "active_enrollments", header: "Active Enrollments", accessor: (r) => r.active_enrollments, format: "number", align: "right", sortable: true, defaultVisible: true },
  { id: "total_spend_ytd", header: "Spend YTD", accessor: (r) => r.total_spend_ytd, format: "currency", align: "right", sortable: true, defaultVisible: true },
  { id: "gtn_ratio", header: "GTN Ratio", accessor: (r) => r.gtn_ratio, defaultVisible: true, align: "right", cell: (v) => <span>{String(v)}%</span> },
];

function ClientProgramsTab({ clientId }: { clientId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["client-programs", clientId],
    queryFn: () => apiGet<{ programs: ProgramSummary[] }>(`/api/v1/clients/${clientId}/programs`),
  });
  return (
    <ConfigurableDataTable
      tableId={`client-programs-${clientId}`}
      columns={PROG_COLS}
      data={data?.programs ?? []}
      loading={isLoading}
      searchable
      pagination={{ pageSize: 25 }}
      emptyMessage="No programs for this client."
    />
  );
}

// ─── Statement Providers tab ──────────────────────────────────────────────────

const SP_COLS: Column<StatementProviderRow>[] = [
  { id: "provider_name", header: "Provider Name", accessor: (r) => r.provider_name, defaultVisible: true, pinned: true },
  { id: "npi", header: "NPI", accessor: (r) => r.npi, defaultVisible: true, cell: (v) => <span className="font-mono text-[13px]">{String(v)}</span> },
  { id: "ncpdp", header: "NCPDP", accessor: (r) => r.ncpdp, defaultVisible: true, cell: (v) => <span className="font-mono text-[13px]">{String(v)}</span> },
  { id: "status", header: "Status", accessor: (r) => r.status, defaultVisible: true, cell: (v) => <StatusBadge status={String(v)} variant={v === "active" ? "success" : "neutral"} /> },
];

function StatementProvidersTab({ clientId }: { clientId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["client-statement-providers", clientId],
    queryFn: () => apiGet<{ providers: StatementProviderRow[] }>(`/api/v1/clients/${clientId}/statement-providers`),
  });
  return (
    <ConfigurableDataTable
      tableId={`statement-providers-${clientId}`}
      columns={SP_COLS}
      data={data?.providers ?? []}
      loading={isLoading}
      searchable
      pagination={{ pageSize: 25 }}
      emptyMessage="No statement providers configured."
    />
  );
}

// ─── Blocked Providers tab ────────────────────────────────────────────────────

const BP_COLS: Column<BlockedProviderRow>[] = [
  { id: "provider_name", header: "Provider Name", accessor: (r) => r.provider_name, defaultVisible: true, pinned: true },
  { id: "npi", header: "NPI", accessor: (r) => r.npi, defaultVisible: true, cell: (v) => <span className="font-mono text-[13px]">{String(v)}</span> },
  { id: "reason", header: "Reason", accessor: (r) => r.reason, defaultVisible: true, width: 300 },
  { id: "blocked_at", header: "Blocked Date", accessor: (r) => r.blocked_at, format: "date", sortable: true, defaultVisible: true },
];

function BlockedProvidersTab({ clientId }: { clientId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["client-blocked-providers", clientId],
    queryFn: () => apiGet<{ blocked: BlockedProviderRow[] }>(`/api/v1/clients/${clientId}/blocked-providers`),
  });
  return (
    <ConfigurableDataTable
      tableId={`blocked-providers-${clientId}`}
      columns={BP_COLS}
      data={data?.blocked ?? []}
      loading={isLoading}
      searchable
      pagination={{ pageSize: 25 }}
      emptyMessage="No blocked providers for this client."
    />
  );
}

// ─── Main Client Detail Page ──────────────────────────────────────────────────

export default function ClientDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [activeTab, setActiveTab] = useState<TabId>("details");

  const { data: client, isLoading } = useQuery({
    queryKey: ["client", id],
    queryFn: () => apiGet<ClientRow>(`/api/v1/clients/${id}`),
    staleTime: 60_000,
  });

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-56 shimmer rounded" />
        <div className="grid grid-cols-4 gap-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-20 shimmer rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  if (!client) {
    return (
      <div className="rounded-lg bg-white ifx-card-shadow p-8 text-center">
        <p className="text-ifx-gray-400">Client not found.</p>
      </div>
    );
  }

  const summaryCards = [
    {
      label: "Programs",
      value: client.programs_count,
      format: "number" as const,
      href: `/clients/${id}?tab=programs`,
      accentColor: "var(--ifx-navy)",
    },
    {
      label: "Status",
      value: client.status === "enabled" ? "Enabled" : "Disabled",
      format: "raw" as const,
      href: "#",
      accentColor: client.status === "enabled" ? "var(--ifx-success)" : "var(--ifx-error)",
    },
    {
      label: "BIN",
      value: client.bin,
      format: "raw" as const,
      href: "#",
      accentColor: "var(--ifx-blue)",
    },
    {
      label: "City / State",
      value: `${client.city}, ${client.state}`,
      format: "raw" as const,
      href: "#",
      accentColor: "var(--ifx-gray-300)",
    },
  ];

  return (
    <DetailPageLayout
      backLink={{ href: "/clients", label: "Back to Companies" }}
      eyebrow="Client Management"
      title={client.company_name}
      subtitle={`Federal ID: ${client.federal_id}`}
      summaryCards={summaryCards}
      summaryColumns={4}
      actions={
        <a
          href={`/clients/portal-access?client=${id}`}
          className="rounded-md border border-ifx-gray-100 bg-white px-4 py-2 text-sm font-medium text-ifx-gray-700 hover:border-ifx-blue hover:text-ifx-blue transition-colors ifx-card-shadow"
        >
          View as Manufacturer
        </a>
      }
    >
      {/* Tabbed sections */}
      <div className="rounded-lg bg-white ifx-card-shadow overflow-hidden">
        <div className="flex border-b border-ifx-gray-100 overflow-x-auto" role="tablist">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              role="tab"
              aria-selected={activeTab === tab.id}
              id={`tab-${tab.id}`}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "whitespace-nowrap px-5 py-3 text-sm font-medium transition-colors border-b-2 -mb-px",
                activeTab === tab.id
                  ? "border-[var(--ifx-navy)] text-ifx-navy"
                  : "border-transparent text-ifx-gray-400 hover:text-ifx-gray-700"
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <div className="p-4" role="tabpanel" aria-labelledby={`tab-${activeTab}`}>
          {activeTab === "details" && <ClientDetailsTab client={client} clientId={id} />}
          {activeTab === "profile" && <ClientProfileTab clientId={id} />}
          {activeTab === "programs" && <ClientProgramsTab clientId={id} />}
          {activeTab === "statement_providers" && <StatementProvidersTab clientId={id} />}
          {activeTab === "blocked_providers" && <BlockedProvidersTab clientId={id} />}
        </div>
      </div>
    </DetailPageLayout>
  );
}
