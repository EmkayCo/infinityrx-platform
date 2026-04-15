"use client";

import { use, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { DetailPageLayout } from "@/components/ui/detail-page-layout";
import { InfoCard } from "@/components/ui/info-card";
import { ConfigurableDataTable, type Column } from "@/components/ui/configurable-data-table";
import { StatusBadge } from "@/components/ui/status-badge";
import { cn } from "@shared/lib/format";
import { apiGet, apiPatch } from "@shared/lib/api-client";
import type { ProgramRow, EnrollmentRow, BudgetMonthRow } from "@shared/lib/mock-data/seed/programs";

// ─── Tabs ─────────────────────────────────────────────────────────────────────

const TABS = [
  { id: "enrollment", label: "Enrollment" },
  { id: "claims", label: "Claims" },
  { id: "leakage", label: "Leakage" },
  { id: "budget", label: "Budget" },
  { id: "configuration", label: "Configuration" },
] as const;
type TabId = (typeof TABS)[number]["id"];

// ─── Enrollment tab ───────────────────────────────────────────────────────────

const ENROLL_COLS: Column<EnrollmentRow>[] = [
  { id: "member_id", header: "Member ID", accessor: (r) => r.member_id, defaultVisible: true, cell: (v) => <span className="font-mono text-[13px]">{String(v)}</span> },
  { id: "enrollment_date", header: "Enrollment Date", accessor: (r) => r.enrollment_date, format: "date", sortable: true, defaultVisible: true },
  { id: "first_fill_date", header: "First Fill", accessor: (r) => r.first_fill_date ?? "—", format: "date", sortable: true, defaultVisible: true },
  { id: "fills_to_date", header: "Fills to Date", accessor: (r) => r.fills_to_date, format: "number", align: "right", sortable: true, defaultVisible: true },
  { id: "spend_to_date", header: "Spend to Date", accessor: (r) => r.spend_to_date, format: "currency", align: "right", sortable: true, defaultVisible: true },
  { id: "status", header: "Status", accessor: (r) => r.status, defaultVisible: true, cell: (v) => <StatusBadge status={String(v)} variant={v === "active" ? "success" : "neutral"} /> },
  { id: "source", header: "Source", accessor: (r) => r.source, defaultVisible: false },
];

function EnrollmentTab({ programId }: { programId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["program-enrollments", programId],
    queryFn: () => apiGet<{ enrollments: EnrollmentRow[] }>(`/api/v1/programs/${programId}/enrollments`),
  });
  return (
    <ConfigurableDataTable
      tableId={`program-enrollments-${programId}`}
      columns={ENROLL_COLS}
      data={data?.enrollments ?? []}
      loading={isLoading}
      searchable
      exportable
      pagination={{ pageSize: 25 }}
      emptyMessage="No enrollments for this program."
    />
  );
}

// ─── Claims tab ───────────────────────────────────────────────────────────────

interface ClaimRow {
  id: string;
  date_of_service: string;
  drug_name: string;
  ndc: string;
  billed_amount: string;
  paid_amount: string;
  status: string;
}

const CLAIM_COLS: Column<ClaimRow>[] = [
  { id: "id", header: "Claim ID", accessor: (r) => r.id, defaultVisible: true, cell: (v) => <span className="font-mono text-[13px]">{String(v)}</span>, pinned: true },
  { id: "date_of_service", header: "Date of Service", accessor: (r) => r.date_of_service, format: "date", sortable: true, defaultVisible: true },
  { id: "drug_name", header: "Drug", accessor: (r) => r.drug_name, defaultVisible: true },
  { id: "ndc", header: "NDC", accessor: (r) => r.ndc, defaultVisible: true, cell: (v) => <span className="font-mono text-[13px]">{String(v)}</span> },
  { id: "billed_amount", header: "Billed", accessor: (r) => r.billed_amount, format: "currency", align: "right", sortable: true, defaultVisible: true },
  { id: "paid_amount", header: "Paid", accessor: (r) => r.paid_amount, format: "currency", align: "right", sortable: true, defaultVisible: true },
  { id: "status", header: "Status", accessor: (r) => r.status, defaultVisible: true, cell: (v) => <StatusBadge status={String(v)} variant={v === "paid" ? "success" : "neutral"} /> },
];

function ClaimsTab({ programId }: { programId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["program-claims", programId],
    queryFn: () => apiGet<{ claims: ClaimRow[] }>(`/api/v1/programs/${programId}/claims`),
  });
  return (
    <ConfigurableDataTable
      tableId={`program-claims-${programId}`}
      columns={CLAIM_COLS}
      data={data?.claims ?? []}
      loading={isLoading}
      searchable
      exportable
      pagination={{ pageSize: 25 }}
      emptyMessage="No claims for this program."
    />
  );
}

// ─── Budget chart tab ─────────────────────────────────────────────────────────

interface BudgetPayload { program_id: string; annual_budget: string; spent: string; remaining: string; projected_annual: string; monthly: BudgetMonthRow[] }

function BudgetTab({ programId }: { programId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["program-budget", programId],
    queryFn: () => apiGet<BudgetPayload>(`/api/v1/programs/${programId}/budget`),
  });

  if (isLoading) return <div className="h-64 shimmer rounded" />;

  const monthly = data?.monthly ?? [];
  const chartData = monthly.map((m) => ({
    month: m.month,
    Budget: parseFloat(m.budget),
    Actual: parseFloat(m.actual),
  }));

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {[
          { label: "Annual Budget", value: data?.annual_budget, format: "currency" as const },
          { label: "Spent to Date", value: data?.spent, format: "currency" as const },
          { label: "Remaining", value: data?.remaining, format: "currency" as const },
          { label: "Projected Year-End", value: data?.projected_annual, format: "currency" as const },
        ].map(({ label, value }) => (
          <div key={label} className="rounded-lg bg-white ifx-card-shadow p-4">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-ifx-gray-400 mb-1">{label}</p>
            <p className="text-lg font-bold text-ifx-gray-900 tabular-nums">
              ${parseFloat(value ?? "0").toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
            </p>
          </div>
        ))}
      </div>
      <div className="rounded-lg bg-white ifx-card-shadow p-4">
        <h4 className="text-sm font-bold text-ifx-gray-900 mb-4">Budget vs. Actual (Monthly)</h4>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={chartData} margin={{ top: 4, right: 16, left: 8, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--ifx-gray-100)" />
            <XAxis dataKey="month" tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}K`} />
            <Tooltip formatter={(v) => typeof v === "number" ? `$${v.toLocaleString("en-US", { minimumFractionDigits: 2 })}` : String(v)} />
            <Legend />
            <Bar dataKey="Budget" fill="var(--ifx-navy)" radius={[3, 3, 0, 0]} />
            <Bar dataKey="Actual" fill="var(--ifx-pink)" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

// ─── Configuration tab ────────────────────────────────────────────────────────

function ConfigurationTab({ program, programId }: { program: ProgramRow; programId: string }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    name: program.name,
    bin: program.bin,
    pcn: program.pcn,
    group_code: program.group_code,
    budget_annual: program.budget_annual,
    max_benefit_per_patient: program.max_benefit_per_patient,
    max_fills_per_patient: program.max_fills_per_patient,
    effective_date: program.effective_date,
    term_date: program.term_date ?? "",
  });
  const [saved, setSaved] = useState(false);

  const mutation = useMutation({
    mutationFn: (data: typeof form) => apiPatch(`/api/v1/programs/${programId}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["program", programId] });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    mutation.mutate(form);
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div className="rounded-lg bg-white ifx-card-shadow p-4">
        <h4 className="text-sm font-bold text-ifx-gray-900 mb-4">Program Settings</h4>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {([
            { name: "name", label: "Program Name", type: "text" },
            { name: "bin", label: "BIN", type: "text" },
            { name: "pcn", label: "PCN", type: "text" },
            { name: "group_code", label: "Group Code", type: "text" },
            { name: "budget_annual", label: "Annual Budget ($)", type: "text" },
            { name: "max_benefit_per_patient", label: "Max Benefit / Patient ($)", type: "text" },
            { name: "max_fills_per_patient", label: "Max Fills / Patient", type: "number" },
            { name: "effective_date", label: "Effective Date", type: "date" },
            { name: "term_date", label: "Term Date", type: "date" },
          ] as const).map((field) => (
            <div key={field.name} className="flex flex-col gap-1">
              <label className="text-[10px] font-semibold uppercase tracking-wider text-ifx-gray-400">
                {field.label}
              </label>
              <input
                type={field.type}
                value={String(form[field.name])}
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
          className="rounded-md bg-[var(--ifx-navy)] px-6 py-2 text-sm font-semibold text-white hover:bg-[var(--ifx-navy-dark)] disabled:opacity-50 transition-colors"
        >
          {mutation.isPending ? "Saving…" : "Save Changes"}
        </button>
        {saved && (
          <span className="text-sm text-green-600">Changes saved.</span>
        )}
        {mutation.isError && (
          <span className="text-sm text-red-500">Save failed — try again.</span>
        )}
      </div>
    </form>
  );
}

// ─── Main Program Detail Page ─────────────────────────────────────────────────

export default function ProgramDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [activeTab, setActiveTab] = useState<TabId>("enrollment");

  const { data: program, isLoading } = useQuery({
    queryKey: ["program", id],
    queryFn: () => apiGet<ProgramRow>(`/api/v1/programs/${id}`),
    staleTime: 60_000,
  });

  const summaryCards = program
    ? [
        { label: "Total Enrollments", value: program.active_enrollments, format: "number" as const, href: "#enrollment" },
        { label: "Total Claims", value: program.total_claims_ytd, format: "number" as const, href: "#claims" },
        { label: "Total Copay Spend", value: program.total_spend_ytd, format: "currency-compact" as const, href: "#budget" },
        { label: "GTN Ratio", value: parseFloat(program.gtn_ratio), format: "percent" as const, href: "/reclaimrx" },
        { label: "Budget Utilization", value: Math.round((parseFloat(program.budget_spent) / parseFloat(program.budget_annual)) * 100), format: "percent" as const, href: "#budget" },
      ]
    : [];

  if (isLoading) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-64 shimmer rounded" />
        <div className="grid grid-cols-5 gap-3">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="h-20 shimmer rounded-lg" />
          ))}
        </div>
      </div>
    );
  }

  if (!program) {
    return (
      <div className="rounded-lg bg-white ifx-card-shadow p-8 text-center">
        <p className="text-ifx-gray-400">Program not found.</p>
      </div>
    );
  }

  return (
    <DetailPageLayout
      backLink={{ href: "/programs", label: "Back to Programs" }}
      eyebrow={program.manufacturer}
      title={program.name}
      subtitle={
        <StatusBadge
          status={program.status}
          variant={program.status === "active" ? "success" : program.status === "paused" ? "warning" : "neutral"}
        />
      }
      summaryCards={summaryCards}
      summaryColumns={5}
      actions={
        <a
          href={`/programs/${id}/configuration`}
          className="rounded-md border border-ifx-gray-100 bg-white px-4 py-2 text-sm font-medium text-ifx-gray-700 hover:border-ifx-blue hover:text-ifx-blue transition-colors ifx-card-shadow"
        >
          Edit Program
        </a>
      }
    >
      {/* Info cards */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <InfoCard
          title="Program Configuration"
          columns={2}
          fields={[
            { label: "Program Name", value: program.name, span: 2 },
            { label: "Manufacturer", value: program.manufacturer },
            { label: "Status", value: <StatusBadge status={program.status} variant={program.status === "active" ? "success" : "warning"} /> },
            { label: "Covered Drugs", value: program.drugs.map((d) => d.name).join(", "), span: 2 },
            { label: "BIN", value: program.bin, mono: true },
            { label: "PCN", value: program.pcn, mono: true },
            { label: "Group Code", value: program.group_code, mono: true },
            { label: "Max Benefit / Patient", value: program.max_benefit_per_patient, format: "currency" },
            { label: "Max Fills / Patient", value: program.max_fills_per_patient },
            { label: "Effective Date", value: program.effective_date, format: "date" },
            { label: "Term Date", value: program.term_date ?? "—" },
          ]}
        />
        <InfoCard
          title="Financial Summary"
          columns={2}
          fields={[
            { label: "Annual Budget", value: program.budget_annual, format: "currency" },
            { label: "Spent to Date", value: program.budget_spent, format: "currency" },
            { label: "Remaining", value: program.budget_remaining, format: "currency" },
            { label: "Projected Year-End", value: program.projected_annual, format: "currency" },
            { label: "Cost per Fill", value: program.cost_per_fill, format: "currency" },
            { label: "Cost per Patient", value: program.cost_per_patient, format: "currency" },
          ]}
        />
      </div>

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
          {activeTab === "enrollment" && <EnrollmentTab programId={id} />}
          {activeTab === "claims" && <ClaimsTab programId={id} />}
          {activeTab === "leakage" && (
            <div className="text-sm text-ifx-gray-400 py-4">
              FWA leakage data for this program — navigate to{" "}
              <a href="/reclaimrx/leakage" className="text-ifx-blue hover:underline">Leakage Monitor</a>{" "}
              for full analysis.
            </div>
          )}
          {activeTab === "budget" && <BudgetTab programId={id} />}
          {activeTab === "configuration" && <ConfigurationTab program={program} programId={id} />}
        </div>
      </div>
    </DetailPageLayout>
  );
}
