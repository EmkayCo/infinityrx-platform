// src/surfaces/pharmacies/PharmacyDetailPage.tsx
// Pharmacy detail page — wraps existing portal detail with Plan A primitives.
// Adds: ProvenanceBadge, FreshnessChip (ncpdp), cross-link to prescriber
// relationships via GET /api/v1/prescribers/relationships/{npi}/pharmacies (router.py:402).
//
// Note on x-tenant-id: the BFF pharmacies/stats route passes ?x-tenant-id={tid}
// (mandatory per pharmacy-directory router.py:442). This page does NOT call
// pharmacy stats directly — the BFF stats route (D-B7) handles that.
"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import { ProvenanceBadge } from "../../components/ProvenanceBadge.js";
import { FreshnessChip } from "../../components/FreshnessChip.js";

export interface PharmacyDetailPageProps {
  npi: string;
  pharmacyDirectoryUrl?: string;
  prescriberDirectoryUrl?: string;
  /** ISO date of last ncpdp ingestion run */
  ncpdp_last_run_at?: string | null;
}

interface PharmacyRecord {
  npi: string;
  name: string;
  city?: string | null;
  state?: string | null;
  pharmacy_type?: string | null;
  network_status?: string | null;
  credentialing_status?: string | null;
  source_date?: string | null;
  run_id?: string | null;
}

interface PrescriberRelationship {
  npi: string;
  display_name: string;
  claim_count: number;
}

interface RelationshipsResponse {
  prescribers: PrescriberRelationship[];
}

export function PharmacyDetailPage({
  npi,
  pharmacyDirectoryUrl = "http://localhost:8009",
  prescriberDirectoryUrl = "http://localhost:8010",
  ncpdp_last_run_at,
}: PharmacyDetailPageProps) {
  const { data: pharmacy, isLoading } = useQuery<PharmacyRecord>({
    queryKey: ["pharmacy-detail", npi],
    queryFn: async () => {
      const url = `${pharmacyDirectoryUrl}/api/v1/pharmacies/lookup/${encodeURIComponent(npi)}`;
      const resp = await fetch(url);
      if (!resp.ok) throw new Error(`pharmacy lookup failed: ${resp.status}`);
      return (await resp.json()) as PharmacyRecord;
    },
    staleTime: 60_000,
  });

  // Cross-link: prescriber relationships via GET /api/v1/prescribers/relationships/{npi}/pharmacies
  // (prescriber-directory router.py:402)
  const { data: relationships } = useQuery<PrescriberRelationship[]>({
    queryKey: ["pharmacy-prescribers", npi],
    queryFn: async () => {
      const url = `${prescriberDirectoryUrl}/api/v1/prescribers/relationships/${encodeURIComponent(npi)}/pharmacies`;
      const resp = await fetch(url);
      if (!resp.ok) return [];
      const body = (await resp.json()) as RelationshipsResponse;
      return body.prescribers ?? [];
    },
    staleTime: 60_000,
    enabled: !!pharmacy,
  });

  if (isLoading) {
    return <div data-testid="pharmacy-detail-loading">Loading...</div>;
  }

  if (!pharmacy) {
    return <div data-testid="pharmacy-not-found">Pharmacy not found.</div>;
  }

  return (
    <div data-testid="pharmacy-detail-page">
      <div data-testid="pharmacy-header">
        <h1 data-testid="pharmacy-name">{pharmacy.name}</h1>
        <p data-testid="pharmacy-npi">NPI: {pharmacy.npi}</p>
        {pharmacy.network_status && (
          <p data-testid="pharmacy-network">{pharmacy.network_status}</p>
        )}
      </div>

      {/* Plan A primitives */}
      <ProvenanceBadge
        sourceKey="ncpdp"
        runId={pharmacy.run_id ?? null}
        sourceDate={pharmacy.source_date ?? null}
      />
      <FreshnessChip
        sourceKey="ncpdp"
        lastRunAt={ncpdp_last_run_at ?? pharmacy.source_date ?? null}
      />

      {/* Prescriber relationships cross-link */}
      {relationships && relationships.length > 0 && (
        <div data-testid="prescriber-relationships">
          <h4>Affiliated Prescribers</h4>
          <ul>
            {relationships.map((r) => (
              <li key={r.npi} data-testid="relationship-row">
                {r.display_name} — NPI: {r.npi} ({r.claim_count} claims)
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
