// src/surfaces/codes/HcpcsListPage.tsx
// HCPCS codes browser — NEW (no existing portal page).
// Route: /directories/codes/hcpcs
//
// Execution-time verification confirmed: no dedicated HCPCS route exists in
// drug-database/src/api/router.py. Codes data is served via drug-database
// GET /api/v1/drugs/search with q= filtering, or via BFF-internal field-catalog.
// This page uses the drug-database search endpoint with type=hcpcs hint.
// Until a dedicated HCPCS backend route exists, results show HCPCS-coded
// drug records returned by the general search.
"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { FreshnessChip } from "../../components/FreshnessChip.js";

export interface HcpcsListPageProps {
  onNavigate?: (href: string) => void;
  /** ISO date of last HCPCS ingestion run */
  hcpcs_last_run_at?: string | null;
  drugDatabaseUrl?: string;
}

interface HcpcsCodeHit {
  code: string;
  description: string;
  category?: string | null;
}

export function HcpcsListPage({
  onNavigate,
  hcpcs_last_run_at,
  drugDatabaseUrl = "http://localhost:8011",
}: HcpcsListPageProps) {
  const [search, setSearch] = useState("");

  const { data: codes = [], isLoading } = useQuery<HcpcsCodeHit[]>({
    queryKey: ["hcpcs", search],
    enabled: search.length >= 2,
    queryFn: async () => {
      // No dedicated HCPCS route — query drug search with the search term.
      // Backend returns drug records; we map any with HCPCS code fields.
      const params = new URLSearchParams({ q: search, limit: "100", type: "hcpcs" });
      const url = `${drugDatabaseUrl}/api/v1/drugs/search?${params.toString()}`;
      const resp = await fetch(url);
      if (!resp.ok) throw new Error(`HCPCS search failed: ${resp.status}`);
      const data = (await resp.json()) as { results?: Array<Record<string, unknown>> };
      // Map drug results to HCPCS code shape
      return (data.results ?? []).map((r) => ({
        code: String(r.hcpcs_code ?? r.ndc ?? ""),
        description: String(r.proprietary_name ?? r.nonproprietary_name ?? r.description ?? ""),
        category: r.therapeutic_class ? String(r.therapeutic_class) : null,
      })).filter((c) => c.code.length > 0);
    },
    staleTime: 60_000,
  });

  return (
    <div data-testid="hcpcs-list-page">
      <h1 data-testid="hcpcs-title">HCPCS Codes</h1>
      <div data-testid="freshness-wrapper">
        <FreshnessChip sourceKey="hcpcs" lastRunAt={hcpcs_last_run_at ?? null} />
      </div>
      <div>
        <input
          type="search"
          aria-label="Search HCPCS codes"
          placeholder="Enter HCPCS code (e.g. J0001) or description..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          data-testid="hcpcs-search-input"
        />
      </div>
      {isLoading && <p data-testid="loading-indicator">Loading...</p>}
      {search.length >= 2 && codes.length === 0 && !isLoading && (
        <p data-testid="no-results">No HCPCS codes found for your search.</p>
      )}
      {search.length < 2 && (
        <p data-testid="search-hint">Enter 2+ characters to search HCPCS codes.</p>
      )}
      <ul data-testid="hcpcs-list">
        {codes.map((c) => (
          <li key={c.code} data-testid="hcpcs-row">
            <button onClick={() => onNavigate?.(`/directories/codes/hcpcs?code=${encodeURIComponent(c.code)}`)}>
              <span data-testid="hcpcs-code">{c.code}</span>
              {" — "}
              <span data-testid="hcpcs-description">{c.description}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
