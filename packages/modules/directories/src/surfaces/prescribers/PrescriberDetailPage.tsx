// src/surfaces/prescribers/PrescriberDetailPage.tsx
// Prescriber detail page — wraps existing portal detail with Plan A primitives.
// Adds: ProvenanceBadge, FreshnessChip (nppes source), ExclusionAlertBadge,
// PrescriberMonitoringPanel (read-only, no acknowledge button per spec §3).
"use client";

import React from "react";
import { useQuery } from "@tanstack/react-query";
import { ProvenanceBadge } from "../../components/ProvenanceBadge.js";
import { FreshnessChip } from "../../components/FreshnessChip.js";
import { ExclusionAlertBadge } from "../../components/ExclusionAlertBadge.js";
import { PrescriberMonitoringPanel } from "./PrescriberMonitoringPanel.js";
import type { ExclusionSource } from "../../components/ExclusionAlertBadge.js";
import type { DatasetKey } from "../../search/schemas.js";

export interface PrescriberDetailPageProps {
  npi: string;
  prescriberDirectoryUrl?: string;
  /** ISO date string of the last NPPES ingestion run */
  nppes_last_run_at?: string | null;
}

interface PrescriberRecord {
  npi: string;
  display_name: string;
  primary_specialty?: string | null;
  source_date?: string | null;
  run_id?: string | null;
}

interface ExclusionCheckResponse {
  sources: DatasetKey[];
}

export function PrescriberDetailPage({
  npi,
  prescriberDirectoryUrl = "http://localhost:8010",
  nppes_last_run_at,
}: PrescriberDetailPageProps) {
  const { data: prescriber, isLoading } = useQuery<PrescriberRecord>({
    queryKey: ["prescriber-detail", npi],
    queryFn: async () => {
      const url = `${prescriberDirectoryUrl}/api/v1/prescribers/lookup/${encodeURIComponent(npi)}`;
      const resp = await fetch(url);
      if (!resp.ok) throw new Error(`prescriber lookup failed: ${resp.status}`);
      return (await resp.json()) as PrescriberRecord;
    },
    staleTime: 60_000,
  });

  // Exclusion cross-check via BFF (D-B3 route).
  const { data: exclusionData } = useQuery<ExclusionCheckResponse>({
    queryKey: ["prescriber-exclusion", npi],
    queryFn: async () => {
      const url = `/api/directories/prescribers/${encodeURIComponent(npi)}/exclusion-check`;
      const resp = await fetch(url);
      if (!resp.ok) return { sources: [] };
      return (await resp.json()) as ExclusionCheckResponse;
    },
    staleTime: 300_000,
  });

  const exclusionSources = (exclusionData?.sources ?? []) as ExclusionSource[];

  if (isLoading) {
    return <div data-testid="prescriber-detail-loading">Loading...</div>;
  }

  if (!prescriber) {
    return <div data-testid="prescriber-not-found">Prescriber not found.</div>;
  }

  return (
    <div data-testid="prescriber-detail-page">
      <div data-testid="prescriber-header">
        <h1 data-testid="prescriber-name">{prescriber.display_name}</h1>
        {prescriber.primary_specialty && (
          <p data-testid="prescriber-specialty">{prescriber.primary_specialty}</p>
        )}
        <p data-testid="prescriber-npi">NPI: {prescriber.npi}</p>
      </div>

      {/* Plan A primitives: data provenance and freshness */}
      <ProvenanceBadge
        sourceKey="nppes"
        runId={prescriber.run_id ?? null}
        sourceDate={prescriber.source_date ?? null}
      />
      <FreshnessChip
        sourceKey="nppes"
        lastRunAt={nppes_last_run_at ?? prescriber.source_date ?? null}
      />

      {/* Exclusion alert — shown when prescriber NPI is in an exclusion list */}
      {exclusionSources.length > 0 && (
        <ExclusionAlertBadge
          npi={npi}
          exclusionSources={exclusionSources}
        />
      )}

      {/* Monitoring panel — read-only (no acknowledge button per spec §3) */}
      <PrescriberMonitoringPanel
        npi={npi}
        prescriberDirectoryUrl={prescriberDirectoryUrl}
      />
    </div>
  );
}
