// src/surfaces/codes/Icd10ListPage.tsx
// ICD-10-CM codes browser — NEW (no existing portal page).
// Route: /directories/codes/icd10
//
// Execution-time verification confirmed: no dedicated ICD-10 route exists in
// drug-database/src/api/router.py. Same approach as HcpcsListPage — uses
// drug-database general search with type=icd10 hint until a dedicated route lands.
"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { FreshnessChip } from "../../components/FreshnessChip.js";

export interface Icd10ListPageProps {
  onNavigate?: (href: string) => void;
  /** ISO date of last ICD-10 ingestion run */
  icd10_last_run_at?: string | null;
  drugDatabaseUrl?: string;
}

interface Icd10CodeHit {
  code: string;
  description: string;
  category?: string | null;
}

export function Icd10ListPage({
  onNavigate,
  icd10_last_run_at,
  drugDatabaseUrl = "http://localhost:8011",
}: Icd10ListPageProps) {
  const [search, setSearch] = useState("");

  const { data: codes = [], isLoading } = useQuery<Icd10CodeHit[]>({
    queryKey: ["icd10", search],
    enabled: search.length >= 2,
    queryFn: async () => {
      const params = new URLSearchParams({ q: search, limit: "100", type: "icd10" });
      const url = `${drugDatabaseUrl}/api/v1/drugs/search?${params.toString()}`;
      const resp = await fetch(url);
      if (!resp.ok) throw new Error(`ICD-10 search failed: ${resp.status}`);
      const data = (await resp.json()) as { results?: Array<Record<string, unknown>> };
      return (data.results ?? []).map((r) => ({
        code: String(r.icd10_code ?? r.code ?? ""),
        description: String(r.description ?? r.proprietary_name ?? ""),
        category: r.category ? String(r.category) : null,
      })).filter((c) => c.code.length > 0);
    },
    staleTime: 60_000,
  });

  return (
    <div data-testid="icd10-list-page">
      <h1 data-testid="icd10-title">ICD-10-CM Codes</h1>
      <div data-testid="freshness-wrapper">
        <FreshnessChip sourceKey="icd10_cm" lastRunAt={icd10_last_run_at ?? null} />
      </div>
      <div>
        <input
          type="search"
          aria-label="Search ICD-10 codes"
          placeholder="Enter ICD-10 code (e.g. E11.9) or description..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          data-testid="icd10-search-input"
        />
      </div>
      {isLoading && <p data-testid="loading-indicator">Loading...</p>}
      {search.length >= 2 && codes.length === 0 && !isLoading && (
        <p data-testid="no-results">No ICD-10 codes found for your search.</p>
      )}
      {search.length < 2 && (
        <p data-testid="search-hint">Enter 2+ characters to search ICD-10 codes.</p>
      )}
      <ul data-testid="icd10-list">
        {codes.map((c) => (
          <li key={c.code} data-testid="icd10-row">
            <button onClick={() => onNavigate?.(`/directories/codes/icd10?code=${encodeURIComponent(c.code)}`)}>
              <span data-testid="icd10-code">{c.code}</span>
              {" — "}
              <span data-testid="icd10-description">{c.description}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
