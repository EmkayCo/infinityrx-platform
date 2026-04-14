"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { ChevronLeft, Phone, MapPin, CheckCircle, XCircle, Clock } from "lucide-react";
import { ErrorBoundary } from "@shared/components/error-boundary";
import { Skeleton } from "@shared/components/skeleton";
import { DataTable, type ColDef } from "@shared/components/data-table";
import { DollarDisplay } from "@shared/components/dollar-display";
import { apiGet, buildUrl } from "@shared/lib/api-client";
import { API_URLS } from "@shared/lib/constants";
import type { Pharmacy } from "@shared/types/directories";
import { cn, formatDate, formatDateTime } from "@shared/lib/format";

interface ClaimRecord {
  id: string;
  date_of_service: string;
  ndc: string;
  drug_name: string;
  billed_amount: string;
  paid_amount: string;
  status: string;
}

const claimColumns: ColDef<ClaimRecord>[] = [
  { accessorKey: "date_of_service", header: "DOS", cell: (c) => formatDate(c.getValue() as string) },
  { accessorKey: "drug_name", header: "Drug" },
  { accessorKey: "ndc", header: "NDC", cell: (c) => <span className="font-mono text-xs">{c.getValue() as string}</span> },
  { accessorKey: "billed_amount", header: "Billed", cell: (c) => <DollarDisplay amount={c.getValue() as string} size="sm" /> },
  { accessorKey: "paid_amount", header: "Paid", cell: (c) => <DollarDisplay amount={c.getValue() as string} size="sm" /> },
  { accessorKey: "status", header: "Status", cell: (c) => <span className="text-xs capitalize text-slate-300">{c.getValue() as string}</span> },
];

interface CredentialCheck {
  name: string;
  status: "pass" | "fail" | "pending";
  detail?: string;
}

const CRED_CHECKS: CredentialCheck[] = [
  { name: "Active state pharmacy license", status: "pass" },
  { name: "NABP accreditation", status: "pass" },
  { name: "DEA registration", status: "pass" },
  { name: "Medicare Part D participation agreement", status: "pass" },
  { name: "HIPAA BAA signed", status: "pending", detail: "Awaiting signature" },
  { name: "Site inspection completed", status: "pass" },
];

export default function PharmacyDetailPage() {
  const { npi } = useParams<{ npi: string }>();
  const router = useRouter();

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
    enabled: !!pharmacy,
    staleTime: 60_000,
  });

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40 rounded-lg" />
        <Skeleton className="h-60 rounded-lg" />
      </div>
    );
  }

  if (!pharmacy) {
    return <div className="p-6"><p className="text-slate-400">Pharmacy not found.</p></div>;
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-4">
        <button
          onClick={() => router.back()}
          className="flex items-center gap-1 text-sm text-slate-400 hover:text-slate-200 transition-colors"
        >
          <ChevronLeft className="w-4 h-4" />
          Back
        </button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-white">{pharmacy.name}</h1>
          <p className="text-slate-400 text-sm">NPI: {pharmacy.npi}</p>
        </div>
        <div className="flex gap-2">
          <span className={cn(
            "text-sm px-3 py-1 rounded-lg capitalize",
            pharmacy.network_status === "in_network" ? "bg-green-900/40 text-green-300" : "bg-slate-700 text-slate-400"
          )}>
            {pharmacy.network_status.replace(/_/g, " ")}
          </span>
          <span className={cn(
            "text-sm px-3 py-1 rounded-lg capitalize",
            pharmacy.credentialing_status === "credentialed" ? "bg-green-900/40 text-green-300" : "bg-yellow-900/40 text-yellow-300"
          )}>
            {pharmacy.credentialing_status}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Demographics */}
        <ErrorBoundary>
          <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5 space-y-3">
            <h3 className="text-sm font-semibold text-slate-200">Details</h3>
            <div className="flex items-start gap-2 text-sm text-slate-400">
              <MapPin className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <span>
                {pharmacy.address_line1}
                {pharmacy.address_line2 && `, ${pharmacy.address_line2}`}
                <br />
                {pharmacy.city}, {pharmacy.state} {pharmacy.zip}
              </span>
            </div>
            {pharmacy.phone && (
              <div className="flex items-center gap-2 text-sm text-slate-400">
                <Phone className="w-4 h-4 flex-shrink-0" />
                {pharmacy.phone}
              </div>
            )}
            <div className="space-y-1 text-xs text-slate-400 pt-2 border-t border-ifx-border-dark">
              <p><span className="text-slate-500">Type:</span> <span className="capitalize">{pharmacy.pharmacy_type.replace(/_/g, " ")}</span></p>
              {pharmacy.ncpdp_id && <p><span className="text-slate-500">NCPDP:</span> {pharmacy.ncpdp_id}</p>}
              {pharmacy.nabp && <p><span className="text-slate-500">NABP:</span> {pharmacy.nabp}</p>}
              {pharmacy.dea_number && <p><span className="text-slate-500">DEA:</span> {pharmacy.dea_number}</p>}
              <p><span className="text-slate-500">Medicaid:</span> {pharmacy.accepts_medicaid ? "Yes" : "No"}</p>
              <p><span className="text-slate-500">Medicare:</span> {pharmacy.accepts_medicare ? "Yes" : "No"}</p>
              <p className="text-slate-500 mt-1">Updated {formatDateTime(pharmacy.updated_at)}</p>
            </div>
          </div>
        </ErrorBoundary>

        {/* Credentialing Checklist */}
        <ErrorBoundary>
          <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
            <h3 className="text-sm font-semibold text-slate-200 mb-4">Credentialing Checklist</h3>
            <div className="space-y-2">
              {CRED_CHECKS.map((check) => (
                <div key={check.name} className="flex items-start gap-2.5">
                  {check.status === "pass" ? (
                    <CheckCircle className="w-4 h-4 text-green-400 flex-shrink-0 mt-0.5" />
                  ) : check.status === "fail" ? (
                    <XCircle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
                  ) : (
                    <Clock className="w-4 h-4 text-yellow-400 flex-shrink-0 mt-0.5" />
                  )}
                  <div>
                    <p className="text-xs text-slate-300">{check.name}</p>
                    {check.detail && <p className="text-xs text-slate-500 mt-0.5">{check.detail}</p>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </ErrorBoundary>

        {/* Placeholder for network adequacy map */}
        <ErrorBoundary>
          <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
            <h3 className="text-sm font-semibold text-slate-200 mb-2">Location</h3>
            <div className="h-40 rounded-lg bg-navy-900/60 border border-ifx-border-dark flex items-center justify-center">
              <div className="text-center">
                <MapPin className="w-8 h-8 text-slate-600 mx-auto mb-2" />
                <p className="text-xs text-slate-500">
                  {pharmacy.city}, {pharmacy.state}
                </p>
              </div>
            </div>
          </div>
        </ErrorBoundary>
      </div>

      {/* Claims History */}
      <ErrorBoundary>
        <div className="rounded-lg border border-ifx-border-dark bg-ifx-surface-dark p-5">
          <h3 className="text-sm font-semibold text-slate-200 mb-4">Claims History</h3>
          <DataTable
            columns={claimColumns}
            data={claims}
            isLoading={claimsLoading}
            emptyTitle="No claims found"
            emptyDescription="No claims on file for this pharmacy."
          />
        </div>
      </ErrorBoundary>
    </div>
  );
}
