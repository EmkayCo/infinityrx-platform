"use client";

import React from "react";
import { use } from "react";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { ArrowLeft, AlertTriangle, CheckCircle, Info } from "lucide-react";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { Skeleton } from "@shared/components/skeleton";
import { DollarDisplay } from "@shared/components/dollar-display";
import { apiGet, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import type { MedicalClaim, MedicalClaimStatus } from "@shared/types/medical-claims";
import { cn, formatDate } from "@shared/lib/format";

export const dynamic = "force-dynamic";

const STATUS_BADGE: Record<MedicalClaimStatus, string> = {
  pending: "bg-yellow-900/40 text-yellow-300",
  approved: "bg-green-900/40 text-green-300",
  denied: "bg-red-900/40 text-red-300",
  adjusted: "bg-blue-900/40 text-blue-300",
  void: "bg-slate-700 text-slate-400",
};

const POS_LABELS: Record<string, string> = {
  "11": "Office",
  "12": "Home",
  "21": "Inpatient Hospital",
  "22": "Outpatient Hospital",
  "23": "Emergency Room",
  "24": "Ambulatory Surgical Center",
  "31": "Skilled Nursing Facility",
  "61": "Inpatient Rehab",
};

const MAPPING_SOURCE_BADGE: Record<string, string> = {
  cms: "bg-blue-900/40 text-blue-300",
  manual: "bg-purple-900/40 text-purple-300",
  ml: "bg-teal-900/40 text-teal-300",
};

function DetailRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between py-2 border-b border-ifx-border-dark/50 last:border-0">
      <span className="text-sm text-slate-400 flex-shrink-0 w-40">{label}</span>
      <div className="text-right">{children}</div>
    </div>
  );
}

export default function MedicalClaimDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();

  const { data: claim, isLoading } = useQuery<MedicalClaim>({
    queryKey: ["medical-claim", id],
    queryFn: () =>
      apiGet<MedicalClaim>(buildUrl(`${API_URLS.medicalClaims}/api/v1/claims/${id}`)),
    staleTime: 30_000,
  });

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-48" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Skeleton className="h-64" />
          <Skeleton className="h-64" />
        </div>
      </div>
    );
  }

  if (!claim) {
    return (
      <div className="p-6">
        <div className="text-center py-16">
          <p className="text-slate-400">Claim not found.</p>
          <button onClick={() => router.back()} className="mt-4 text-teal-400 hover:text-teal-300 text-sm">
            Go back
          </button>
        </div>
      </div>
    );
  }

  const wasteUnits = claim.waste_units ?? 0;
  const hasWaste = wasteUnits > 0;
  const mapping = claim.hcpcs_ndc_mapping;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start gap-3">
        <button onClick={() => router.back()} className="mt-1 text-slate-400 hover:text-slate-200 transition-colors">
          <ArrowLeft className="w-5 h-5" />
        </button>
        <div className="flex-1">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-2xl font-bold text-white font-mono">{claim.claim_number}</h1>
            <span className={cn("text-xs px-2 py-0.5 rounded capitalize", STATUS_BADGE[claim.status])}>
              {claim.status}
            </span>
            {claim.is_340b && (
              <span className="text-xs px-2 py-0.5 rounded bg-purple-900/40 text-purple-300">
                340B
              </span>
            )}
          </div>
          <p className="text-slate-400 text-sm mt-1">
            Date of Service: {formatDate(claim.date_of_service)} &nbsp;·&nbsp; Submitted: {formatDate(claim.created_at)}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Claim Details */}
        <ErrorBoundary>
          <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
            <h3 className="text-sm font-semibold text-slate-200 mb-4">Claim Details</h3>
            <DetailRow label="Claim Number">
              <span className="font-mono text-xs text-slate-300">{claim.claim_number}</span>
            </DetailRow>
            <DetailRow label="Provider">
              <div className="text-right">
                <p className="text-sm text-slate-200">{claim.provider_name}</p>
                <p className="text-xs text-slate-500 font-mono">NPI: {claim.provider_npi}</p>
              </div>
            </DetailRow>
            <DetailRow label="Member">
              <span className="text-sm text-slate-200">{claim.masked_member_name}</span>
            </DetailRow>
            <DetailRow label="Place of Service">
              <div className="text-right">
                <p className="text-sm text-slate-200">{POS_LABELS[claim.place_of_service] ?? claim.place_of_service}</p>
                <p className="text-xs text-slate-500">POS {claim.place_of_service}</p>
              </div>
            </DetailRow>
            <DetailRow label="HCPCS Code">
              <div className="text-right">
                <p className="font-mono text-sm text-teal-400">{claim.hcpcs_code}</p>
                {claim.hcpcs_description && (
                  <p className="text-xs text-slate-400">{claim.hcpcs_description}</p>
                )}
              </div>
            </DetailRow>
            {claim.ndc && (
              <DetailRow label="NDC">
                <div className="text-right">
                  <p className="font-mono text-sm text-slate-300">{claim.ndc}</p>
                  {claim.drug_name && <p className="text-xs text-slate-400">{claim.drug_name}</p>}
                </div>
              </DetailRow>
            )}
            <DetailRow label="Units Billed">
              <span className="text-sm text-slate-300 tabular-nums">{claim.units_billed}</span>
            </DetailRow>
            {claim.units_administered !== undefined && (
              <DetailRow label="Units Administered">
                <span className="text-sm text-slate-300 tabular-nums">{claim.units_administered}</span>
              </DetailRow>
            )}
          </div>
        </ErrorBoundary>

        {/* Financial Breakdown */}
        <ErrorBoundary>
          <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
            <h3 className="text-sm font-semibold text-slate-200 mb-4">Financial Breakdown</h3>
            <DetailRow label="Billed Amount">
              <DollarDisplay amount={claim.billed_amount} size="md" />
            </DetailRow>
            {claim.allowed_amount && (
              <DetailRow label="Allowed Amount">
                <DollarDisplay amount={claim.allowed_amount} size="md" />
              </DetailRow>
            )}
            {claim.paid_amount && (
              <DetailRow label="Paid Amount">
                <DollarDisplay amount={claim.paid_amount} size="md" />
              </DetailRow>
            )}
            {claim.patient_responsibility && (
              <DetailRow label="Patient Responsibility">
                <DollarDisplay amount={claim.patient_responsibility} size="md" />
              </DetailRow>
            )}

            {/* ASP Pricing */}
            {(claim.asp_unit_price || claim.asp_total) && (
              <>
                <div className="mt-4 mb-2">
                  <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">ASP Pricing</p>
                </div>
                {claim.asp_unit_price && (
                  <DetailRow label="ASP Unit Price">
                    <DollarDisplay amount={claim.asp_unit_price} size="sm" />
                  </DetailRow>
                )}
                {claim.asp_total && (
                  <DetailRow label="ASP Total">
                    <DollarDisplay amount={claim.asp_total} size="md" />
                  </DetailRow>
                )}
              </>
            )}

            {/* Waste */}
            {hasWaste && (
              <div className="mt-4 rounded-lg bg-red-900/20 border border-red-800/40 p-3">
                <div className="flex items-center gap-2 mb-2">
                  <AlertTriangle className="w-4 h-4 text-red-400" />
                  <p className="text-sm font-semibold text-red-300">Drug Waste Detected</p>
                </div>
                <div className="space-y-1">
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-400">Waste Units</span>
                    <span className="text-red-300 tabular-nums">{wasteUnits}</span>
                  </div>
                  {claim.waste_amount && (
                    <div className="flex justify-between text-xs">
                      <span className="text-slate-400">Waste Amount</span>
                      <DollarDisplay amount={claim.waste_amount} size="sm" />
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </ErrorBoundary>
      </div>

      {/* HCPCS → NDC Mapping Panel */}
      {mapping && (
        <ErrorBoundary>
          <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
            <div className="flex items-center gap-2 mb-4">
              <h3 className="text-sm font-semibold text-slate-200">HCPCS → NDC Mapping</h3>
              <span className={cn("text-xs px-2 py-0.5 rounded uppercase", MAPPING_SOURCE_BADGE[mapping.mapping_source])}>
                {mapping.mapping_source}
              </span>
            </div>

            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
              <div>
                <p className="text-xs text-slate-400 mb-1">HCPCS Code</p>
                <p className="font-mono text-sm text-teal-400">{mapping.hcpcs}</p>
              </div>
              <div>
                <p className="text-xs text-slate-400 mb-1">NDC</p>
                <p className="font-mono text-sm text-slate-300">{mapping.ndc}</p>
              </div>
              <div>
                <p className="text-xs text-slate-400 mb-1">Drug / Strength</p>
                <p className="text-sm text-slate-300">{mapping.drug_name}</p>
                <p className="text-xs text-slate-500">{mapping.strength}</p>
              </div>
              <div>
                <p className="text-xs text-slate-400 mb-1">Units per Claim</p>
                <p className="text-sm text-slate-300 tabular-nums">{mapping.units_per_claim}</p>
              </div>
            </div>

            {/* Confidence Score */}
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-1.5">
                  <Info className="w-3 h-3 text-slate-500" />
                  <span className="text-xs text-slate-400">Mapping Confidence</span>
                </div>
                <span className={cn(
                  "text-xs font-semibold",
                  mapping.confidence_score >= 0.9 ? "text-green-400" : mapping.confidence_score >= 0.7 ? "text-yellow-400" : "text-red-400"
                )}>
                  {(mapping.confidence_score * 100).toFixed(0)}%
                </span>
              </div>
              <div className="h-2 rounded-full bg-navy-700">
                <div
                  className={cn(
                    "h-full rounded-full transition-all",
                    mapping.confidence_score >= 0.9 ? "bg-green-400" : mapping.confidence_score >= 0.7 ? "bg-yellow-400" : "bg-red-400"
                  )}
                  style={{ width: `${mapping.confidence_score * 100}%` }}
                />
              </div>
              {mapping.confidence_score < 0.9 && (
                <p className="text-xs text-yellow-400 mt-1.5 flex items-center gap-1">
                  <AlertTriangle className="w-3 h-3" />
                  Low confidence mapping — manual review recommended
                </p>
              )}
            </div>

            {mapping.effective_date && (
              <p className="text-xs text-slate-500 mt-3">
                Effective: {formatDate(mapping.effective_date)}
              </p>
            )}
          </div>
        </ErrorBoundary>
      )}

      {/* 340B Notice */}
      {claim.is_340b && (
        <ErrorBoundary>
          <div className="rounded-lg border border-purple-800/40 bg-purple-900/10 p-4">
            <div className="flex items-start gap-3">
              <CheckCircle className="w-5 h-5 text-purple-400 mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-sm font-semibold text-purple-300">340B Program Claim</p>
                <p className="text-xs text-slate-400 mt-0.5">
                  This claim has been flagged as a 340B-eligible transaction. The covered entity may be
                  eligible to purchase the drug at the 340B ceiling price.
                </p>
                <button
                  onClick={() => router.push("/medical-claims/340b")}
                  className="text-xs text-purple-400 hover:text-purple-300 mt-2 underline"
                >
                  View 340B Summary →
                </button>
              </div>
            </div>
          </div>
        </ErrorBoundary>
      )}
    </div>
  );
}
