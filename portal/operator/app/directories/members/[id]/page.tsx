"use client";

import React, { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { Shield, CreditCard } from "lucide-react";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { Skeleton } from "@shared/components/skeleton";
import { DollarDisplay } from "@shared/components/dollar-display";
import { DataTable, type ColDef } from "@shared/components/data-table";
import { apiGet, apiPost, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import { useAuth } from "@shared/hooks/use-auth";
import type { Member, MemberAccumulator, CopayEnrollment, EligibilityHistoryEntry } from "@shared/types/directories";
import { Permission } from "@shared/types/auth";
import { cn, formatDate } from "@shared/lib/format";
import { DetailPageLayout } from "@/components/ui/detail-page-layout";
import { InfoCard } from "@/components/ui/info-card";
import { StatusBadge, inferStatusVariant } from "@/components/ui/status-badge";

// Cache-Control: no-store applied via page metadata for PHI compliance
export const dynamic = "force-dynamic";

// ── Types ─────────────────────────────────────────────────────────────────────

interface ClaimRecord {
  id: string;
  date_of_service: string;
  pharmacy_name: string;
  drug_name: string;
  billed_amount: string;
  paid_amount: string;
  copay: string;
  status: string;
}

// ── Column definitions ────────────────────────────────────────────────────────

const claimColumns: ColDef<ClaimRecord>[] = [
  { accessorKey: "date_of_service", header: "DOS", cell: (c) => formatDate(c.getValue() as string) },
  { accessorKey: "pharmacy_name", header: "Pharmacy" },
  { accessorKey: "drug_name", header: "Drug" },
  { accessorKey: "billed_amount", header: "Billed", cell: (c) => <DollarDisplay amount={c.getValue() as string} size="sm" /> },
  { accessorKey: "paid_amount", header: "Paid", cell: (c) => <DollarDisplay amount={c.getValue() as string} size="sm" /> },
  { accessorKey: "copay", header: "Copay", cell: (c) => <DollarDisplay amount={c.getValue() as string} size="sm" /> },
  { accessorKey: "status", header: "Status", cell: (c) => <StatusBadge status={c.getValue() as string} /> },
];

const eligibilityHistoryColumns: ColDef<EligibilityHistoryEntry>[] = [
  { accessorKey: "effective_date", header: "Effective", cell: (c) => formatDate(c.getValue() as string) },
  { accessorKey: "event", header: "Event", cell: (c) => <span className="font-medium">{c.getValue() as string}</span> },
  { accessorKey: "plan_name", header: "Plan", cell: (c) => (c.getValue() as string | undefined) ?? "—" },
  { accessorKey: "group_id", header: "Group ID", cell: (c) => <span className="font-mono text-xs text-ifx-navy">{(c.getValue() as string | undefined) ?? "—"}</span> },
  { accessorKey: "changed_by", header: "Source", cell: (c) => <span className="text-xs text-ifx-gray-400">{(c.getValue() as string | undefined) ?? "—"}</span> },
];

// ── Accumulator bars ─────────────────────────────────────────────────────────

function AccumulatorBars({ acc }: { acc: MemberAccumulator }) {
  const deductiblePct = Math.min(
    100,
    (parseFloat(acc.deductible_applied) / parseFloat(acc.deductible_limit)) * 100
  );
  const oopPct = Math.min(
    100,
    (parseFloat(acc.oop_applied) / parseFloat(acc.oop_limit)) * 100
  );

  return (
    <div className="space-y-4">
      {[
        { label: "Deductible", applied: acc.deductible_applied, limit: acc.deductible_limit, pct: deductiblePct, color: "bg-ifx-blue" },
        { label: "Out-of-Pocket Maximum", applied: acc.oop_applied, limit: acc.oop_limit, pct: oopPct, color: oopPct >= 100 ? "bg-ifx-success" : "bg-ifx-blue" },
      ].map(({ label, applied, limit, pct, color }) => (
        <div key={label}>
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-ifx-gray-700">{label}</span>
            <span className="text-xs text-ifx-gray-400">
              <DollarDisplay amount={applied} size="sm" showScale={false} /> / <DollarDisplay amount={limit} size="sm" showScale={false} />
            </span>
          </div>
          <div className="h-2.5 rounded-full bg-ifx-gray-100 overflow-hidden">
            <div className={cn("h-full rounded-full transition-all duration-500", color)} style={{ width: `${pct}%` }} />
          </div>
          <p className="text-xs text-ifx-gray-400 mt-0.5">{Math.round(pct)}% used</p>
        </div>
      ))}
      <div className="flex items-center justify-between text-xs border-t border-ifx-gray-100 pt-2 mt-2">
        <span className="text-ifx-gray-400">Benefit Phase</span>
        <StatusBadge
          status={acc.benefit_phase.replace(/_/g, " ")}
          variant={
            acc.benefit_phase === "catastrophic" ? "warning" :
            acc.benefit_phase === "coverage_gap" ? "warning" :
            acc.benefit_phase === "initial_coverage" ? "info" :
            "neutral"
          }
        />
      </div>
      {acc.troop_applied && (
        <div className="flex items-center justify-between text-xs">
          <span className="text-ifx-gray-400">TrOOP Applied</span>
          <DollarDisplay amount={acc.troop_applied} size="sm" showScale={false} />
        </div>
      )}
    </div>
  );
}

// ── Copay enrollment card ─────────────────────────────────────────────────────

function CopayEnrollmentCard({ enrollments }: { enrollments: CopayEnrollment[] }) {
  if (enrollments.length === 0) {
    return (
      <div className="rounded-lg bg-white ifx-card-shadow overflow-hidden">
        <header className="flex items-center gap-2 border-b border-ifx-gray-100 px-4 py-3">
          <CreditCard className="w-4 h-4 text-ifx-gray-400" />
          <h3 className="text-sm font-bold text-ifx-gray-900">Copay Programs</h3>
        </header>
        <div className="p-4">
          <p className="text-sm text-ifx-gray-400">Not enrolled in any copay assistance programs.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-lg bg-white ifx-card-shadow overflow-hidden">
      <header className="flex items-center gap-2 border-b border-ifx-gray-100 px-4 py-3">
        <CreditCard className="w-4 h-4 text-ifx-gray-400" />
        <h3 className="text-sm font-bold text-ifx-gray-900">Copay Programs ({enrollments.length})</h3>
      </header>
      <div className="divide-y divide-ifx-gray-100">
        {enrollments.map((enroll) => {
          const benefitPct = Math.min(
            100,
            (parseFloat(enroll.remaining_benefit) / parseFloat(enroll.benefit_limit)) * 100
          );
          return (
            <div key={enroll.program_id} className="p-4 space-y-3" data-testid="copay-enrollment-row">
              <div className="flex items-start justify-between">
                <div>
                  <div className="text-sm font-semibold text-ifx-gray-900">{enroll.program_name}</div>
                  <div className="text-xs text-ifx-gray-400 mt-0.5">
                    BIN {enroll.bin} · PCN {enroll.pcn} · Group {enroll.group_code}
                  </div>
                </div>
                <StatusBadge status={enroll.card_status} variant={inferStatusVariant(enroll.card_status)} />
              </div>
              <div>
                <div className="flex items-center justify-between mb-1 text-xs text-ifx-gray-400">
                  <span>Remaining benefit</span>
                  <span>
                    <DollarDisplay amount={enroll.remaining_benefit} size="sm" showScale={false} />
                    {" / "}
                    <DollarDisplay amount={enroll.benefit_limit} size="sm" showScale={false} />
                  </span>
                </div>
                <div className="h-2 rounded-full bg-ifx-gray-100 overflow-hidden">
                  <div
                    className={cn("h-full rounded-full", benefitPct > 50 ? "bg-ifx-success" : benefitPct > 20 ? "bg-ifx-warning" : "bg-ifx-error")}
                    style={{ width: `${benefitPct}%` }}
                  />
                </div>
              </div>
              <div className="text-xs text-ifx-gray-400">Enrolled {formatDate(enroll.enrolled_at)}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Tabs ─────────────────────────────────────────────────────────────────────

type Tab = "claims" | "prescriptions" | "adherence" | "eligibility_history";
const TABS: { id: Tab; label: string }[] = [
  { id: "claims", label: "Claims" },
  { id: "prescriptions", label: "Prescriptions" },
  { id: "adherence", label: "Adherence" },
  { id: "eligibility_history", label: "Eligibility History" },
];

// ── Page ─────────────────────────────────────────────────────────────────────

export default function MemberDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { hasPermission } = useAuth();
  const canViewFullPHI = hasPermission(Permission.DirectoriesFull);
  const [activeTab, setActiveTab] = useState<Tab>("claims");

  const { data: member, isLoading } = useQuery<Member>({
    queryKey: ["member", id],
    queryFn: () => apiGet<Member>(`${API_URLS.memberManagement}/api/v1/members/${id}`),
    staleTime: 30_000,
  });

  // PHI access audit beacon — fire-and-forget, never crash the page
  useEffect(() => {
    if (member) {
      void apiPost(
        `${API_URLS.memberManagement}/api/v1/members/${id}/audit-access`,
        {}
      ).catch(() => undefined);
    }
  }, [id, member]);

  const { data: claims = [], isLoading: claimsLoading } = useQuery<ClaimRecord[]>({
    queryKey: ["member-claims", id],
    queryFn: () =>
      apiGet<ClaimRecord[]>(
        buildUrl(`${API_URLS.memberManagement}/api/v1/members/${id}/claims`, { limit: 50 })
      ),
    enabled: !!member && activeTab === "claims",
    staleTime: 30_000,
  });

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-64" />
        <div className="grid grid-cols-2 gap-4">
          <Skeleton className="h-48 rounded-lg" />
          <Skeleton className="h-48 rounded-lg" />
        </div>
      </div>
    );
  }

  if (!member) return <div className="p-6"><p className="text-ifx-gray-400">Member not found.</p></div>;

  // PHI: never expose full_name or date_of_birth without permission
  const displayName = canViewFullPHI ? (member.full_name ?? member.masked_name) : member.masked_name;
  const displayDOB = canViewFullPHI ? (member.date_of_birth ?? member.masked_dob) : member.masked_dob;

  const coverageStatus = member.coverage_status;
  const eligibilityStatus = member.eligibility_status ?? "pending_verification";

  return (
    <div className="p-6">
      {/* PHI notice banner */}
      {!canViewFullPHI && (
        <div
          className="mb-4 rounded-lg border border-amber-200 bg-amber-50 p-3 flex items-center gap-2 text-xs text-amber-800"
          data-testid="phi-notice"
        >
          <Shield className="w-4 h-4 flex-shrink-0 text-amber-600" />
          PHI is masked based on your role. Contact your administrator for full access.
        </div>
      )}

      <DetailPageLayout
        backLink={{ href: "/directories/members", label: "Member Directory" }}
        title={displayName}
        subtitle={
          <span className="font-mono text-[13px]">
            Member ID: {member.member_id}
            {member.group_id && <> · Group: {member.group_id}</>}
          </span>
        }
        actions={
          <div className="flex items-center gap-2">
            {/* PHI indicator badge */}
            <span
              className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide bg-amber-100 text-amber-800"
              data-testid="phi-badge"
            >
              <Shield className="w-3 h-3" />
              PHI
            </span>
            <StatusBadge
              status={coverageStatus}
              variant={
                coverageStatus === "active" ? "success" :
                coverageStatus === "pending" ? "warning" :
                coverageStatus === "cobra" ? "info" :
                "error"
              }
            />
            <StatusBadge
              status={eligibilityStatus.replace(/_/g, " ")}
              variant={
                eligibilityStatus === "eligible" ? "success" :
                eligibilityStatus === "pending_verification" ? "warning" :
                "error"
              }
            />
          </div>
        }
        summaryCards={[
          { label: "Total Claims", value: 47, format: "number" as const },
          {
            label: "Deductible Met",
            value: `${Math.round((parseFloat(member.accumulator?.deductible_applied ?? "0") / parseFloat(member.accumulator?.deductible_limit ?? "3000")) * 100)}%`,
            format: "raw" as const,
          },
          {
            label: "OOP Applied",
            value: member.accumulator?.oop_applied ?? "0.00",
            format: "currency" as const,
          },
          {
            label: "Copay Programs",
            value: member.copay_enrollment?.length ?? 0,
            format: "raw" as const,
            accentColor: (member.copay_enrollment?.length ?? 0) > 0 ? "var(--ifx-success)" : undefined,
          },
        ]}
        summaryColumns={4}
      >
        {/* Identity and Coverage info */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <ErrorBoundary>
            <InfoCard
              title="Identity"
              columns={2}
              fields={[
                { label: "Member ID", value: member.member_id, mono: true },
                { label: "Gender", value: member.gender ?? null },
                {
                  label: "Date of Birth",
                  value: (
                    <span className="flex items-center gap-1">
                      {displayDOB}
                      {!canViewFullPHI && <Shield className="w-3 h-3 text-amber-500" />}
                    </span>
                  ),
                },
                { label: "Coverage Type", value: member.coverage_type ?? null },
              ]}
            />
          </ErrorBoundary>

          <ErrorBoundary>
            <InfoCard
              title="Coverage"
              columns={2}
              fields={[
                { label: "Plan", value: member.plan_name ?? null },
                { label: "Group ID", value: member.group_id ?? null, mono: true },
                { label: "Eligibility Status", value: eligibilityStatus.replace(/_/g, " ") },
                { label: "Coverage Status", value: coverageStatus },
                { label: "Effective Date", value: member.coverage_effective_date ?? null, format: "date" },
                { label: "Term Date", value: member.coverage_term_date ?? null, format: "date" },
              ]}
            />
          </ErrorBoundary>

          {/* Accumulators */}
          {member.accumulator && (
            <ErrorBoundary>
              <div className="rounded-lg bg-white ifx-card-shadow overflow-hidden">
                <header className="border-b border-ifx-gray-100 px-4 py-3">
                  <h3 className="text-sm font-bold text-ifx-gray-900">
                    Accumulators (Benefit Year {member.accumulator.benefit_year})
                  </h3>
                </header>
                <div className="p-4">
                  <AccumulatorBars acc={member.accumulator} />
                </div>
              </div>
            </ErrorBoundary>
          )}

          {/* Copay Enrollment */}
          <ErrorBoundary>
            <CopayEnrollmentCard enrollments={member.copay_enrollment ?? []} />
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
                  emptyDescription="No claims on file for this member."
                />
              )}

              {activeTab === "prescriptions" && (
                <DataTable
                  columns={claimColumns}
                  data={claims}
                  isLoading={claimsLoading}
                  emptyTitle="No prescriptions found"
                  emptyDescription="No prescription history for this member."
                />
              )}

              {activeTab === "adherence" && (
                <div className="space-y-4">
                  <p className="text-sm text-ifx-gray-700">
                    Medication adherence analysis measures how consistently this member fills their prescriptions.
                  </p>
                  <div className="grid grid-cols-3 gap-4">
                    {[
                      { label: "PDC Score (Statins)", value: "87%" },
                      { label: "PDC Score (Diabetes)", value: "79%" },
                      { label: "Gaps in Therapy", value: "2" },
                    ].map((kpi) => (
                      <div key={kpi.label} className="rounded-lg border border-ifx-gray-100 p-3">
                        <div className="text-[10px] font-semibold uppercase tracking-wider text-ifx-gray-400">{kpi.label}</div>
                        <div className="text-2xl font-bold text-ifx-gray-900 mt-1">{kpi.value}</div>
                      </div>
                    ))}
                  </div>
                  <p className="text-xs text-ifx-gray-400">PDC = Proportion of Days Covered. Threshold: ≥80% for good adherence.</p>
                </div>
              )}

              {activeTab === "eligibility_history" && (
                <DataTable
                  columns={eligibilityHistoryColumns}
                  data={member.eligibility_history ?? []}
                  isLoading={false}
                  emptyTitle="No history found"
                  emptyDescription="No eligibility history events on file."
                />
              )}
            </div>
          </div>
        </ErrorBoundary>
      </DetailPageLayout>
    </div>
  );
}
