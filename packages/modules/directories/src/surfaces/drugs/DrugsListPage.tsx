// src/surfaces/drugs/DrugsListPage.tsx
// Drug database list page - shows search results as a readable table.
// API: GET /api/v1/drugs/search -> { results: [...], total }
// Fields: ndc_11, ndc_formatted, drug_name_display, proprietary_name, dosage_form, strength, labeler_name
"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { FreshnessChip } from "../../components/FreshnessChip.js";

export interface DrugsListPageProps {
  onNavigate?: (href: string) => void;
  /** ISO date of last fda_ndc ingestion run */
  fda_ndc_last_run_at?: string | null;
  drugDatabaseUrl?: string;
}

interface DrugSearchHit {
  ndc_11?: string | null;
  ndc_formatted?: string | null;
  drug_name_display?: string | null;
  proprietary_name?: string | null;
  nonproprietary_name?: string | null;
  dosage_form?: string | null;
  strength?: string | null;
  labeler_name?: string | null;
}

export function DrugsListPage({
  onNavigate,
  fda_ndc_last_run_at,
  drugDatabaseUrl = "http://localhost:8011",
}: DrugsListPageProps) {
  const [search, setSearch] = useState("");

  const { data: drugs = [], isLoading, error } = useQuery<DrugSearchHit[]>({
    queryKey: ["drugs", search],
    queryFn: async () => {
      const params = new URLSearchParams({ limit: "100" });
      if (search) params.set("q", search);
      const url = `${drugDatabaseUrl}/api/v1/drugs/search?${params.toString()}`;
      const resp = await fetch(url, {
        headers: { "x-tenant-id": "a0000000-0000-0000-0000-000000000001" },
      });
      if (!resp.ok) throw new Error(`drugs search failed: ${resp.status}`);
      const data = (await resp.json()) as { results?: DrugSearchHit[]; drugs?: DrugSearchHit[] };
      return data.results ?? data.drugs ?? [];
    },
    staleTime: 60_000,
  });

  return (
    <div data-testid="drugs-list-page" style={{ padding: "16px" }}>
      <div data-testid="freshness-wrapper" style={{ marginBottom: "12px" }}>
        <FreshnessChip sourceKey="fda_ndc" lastRunAt={fda_ndc_last_run_at ?? null} />
      </div>
      <div style={{ marginBottom: "12px" }}>
        <input
          type="search"
          aria-label="Search drugs"
          placeholder="Search NDC, drug name, therapeutic class..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          data-testid="drugs-search-input"
          style={{ width: "100%", maxWidth: "480px", padding: "8px 12px", fontSize: "14px", border: "1px solid #d1d5db", borderRadius: "6px" }}
        />
      </div>
      {isLoading && <p data-testid="loading-indicator">Loading...</p>}
      {error && <p style={{ color: "#dc2626" }}>Error loading drugs.</p>}
      {!isLoading && !error && drugs.length === 0 && search.length >= 2 && (
        <p data-testid="no-results">No drugs found for &quot;{search}&quot;.</p>
      )}
      {!isLoading && !error && drugs.length === 0 && search.length < 2 && (
        <p data-testid="empty-hint" style={{ color: "#6b7280", fontSize: "14px" }}>
          Enter 2 or more characters to search drugs.
        </p>
      )}
      {drugs.length > 0 && (
        <div style={{ overflowX: "auto" }}>
          <table
            data-testid="drugs-list"
            style={{ width: "100%", borderCollapse: "collapse", fontSize: "14px" }}
          >
            <thead>
              <tr style={{ borderBottom: "2px solid #e5e7eb", textAlign: "left", backgroundColor: "#f9fafb" }}>
                <th style={{ padding: "8px 12px", fontWeight: 600, color: "#374151" }}>Name</th>
                <th style={{ padding: "8px 12px", fontWeight: 600, color: "#374151" }}>NDC-11</th>
                <th style={{ padding: "8px 12px", fontWeight: 600, color: "#374151" }}>Form</th>
                <th style={{ padding: "8px 12px", fontWeight: 600, color: "#374151" }}>Strength</th>
                <th style={{ padding: "8px 12px", fontWeight: 600, color: "#374151" }}>Manufacturer</th>
              </tr>
            </thead>
            <tbody>
              {drugs.map((d, idx) => (
                <tr
                  key={d.ndc_11 ?? String(idx)}
                  data-testid="drug-row"
                  onClick={() => onNavigate?.(`/directories/drugs/${d.ndc_11}`)}
                  style={{
                    borderBottom: "1px solid #f3f4f6",
                    cursor: onNavigate ? "pointer" : "default",
                    backgroundColor: idx % 2 === 0 ? "#ffffff" : "#f9fafb",
                  }}
                >
                  <td style={{ padding: "8px 12px", fontWeight: 500 }}>
                    {d.drug_name_display ?? d.proprietary_name ?? d.nonproprietary_name ?? "-"}
                  </td>
                  <td style={{ padding: "8px 12px", fontFamily: "monospace", fontSize: "13px" }}>
                    {d.ndc_formatted ?? d.ndc_11 ?? "-"}
                  </td>
                  <td style={{ padding: "8px 12px", color: "#6b7280" }}>{d.dosage_form ?? "-"}</td>
                  <td style={{ padding: "8px 12px", color: "#6b7280" }}>{d.strength ?? "-"}</td>
                  <td style={{ padding: "8px 12px", color: "#6b7280" }}>{d.labeler_name ?? "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p style={{ marginTop: "8px", fontSize: "12px", color: "#6b7280" }}>
            {drugs.length} result{drugs.length !== 1 ? "s" : ""}
          </p>
        </div>
      )}
    </div>
  );
}
