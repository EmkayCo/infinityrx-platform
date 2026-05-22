// src/surfaces/pharmacies/PharmaciesListPage.tsx
// Pharmacy directory list page - shows search results as a readable table.
// API: GET /api/v1/pharmacies/search -> { pharmacies: [...], total }
// Fields: npi, display_name, legal_name, nabp_number, city, state, status
"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { FreshnessChip } from "../../components/FreshnessChip.js";

export interface PharmaciesListPageProps {
  onNavigate?: (href: string) => void;
  ncpdp_last_run_at?: string | null;
  pharmacyDirectoryUrl?: string;
}

interface PharmacySearchHit {
  npi: string;
  display_name?: string | null;
  legal_name?: string | null;
  nabp_number?: string | null;
  city?: string | null;
  state?: string | null;
  status?: string | null;
}

export function PharmaciesListPage({
  onNavigate,
  ncpdp_last_run_at,
  pharmacyDirectoryUrl = "http://localhost:8009",
}: PharmaciesListPageProps) {
  const [search, setSearch] = useState("");

  const { data: pharmacies = [], isLoading, error } = useQuery<PharmacySearchHit[]>({
    queryKey: ["pharmacies", search],
    queryFn: async () => {
      const params = new URLSearchParams({ limit: "100" });
      if (search) params.set("q", search);
      const url = `${pharmacyDirectoryUrl}/api/v1/pharmacies/search?${params.toString()}`;
      const resp = await fetch(url, {
        headers: { "x-tenant-id": "a0000000-0000-0000-0000-000000000001" },
      });
      if (!resp.ok) throw new Error(`pharmacies search failed: ${resp.status}`);
      const data = (await resp.json()) as { pharmacies?: PharmacySearchHit[]; results?: PharmacySearchHit[] };
      return data.pharmacies ?? data.results ?? [];
    },
    staleTime: 60_000,
  });

  return (
    <div data-testid="pharmacies-list-page" style={{ padding: "16px" }}>
      <div data-testid="freshness-wrapper" style={{ marginBottom: "12px" }}>
        <FreshnessChip sourceKey="ncpdp" lastRunAt={ncpdp_last_run_at ?? null} />
      </div>
      <div style={{ marginBottom: "12px" }}>
        <input
          type="search"
          aria-label="Search pharmacies"
          placeholder="Search NPI, name, city, state..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          data-testid="pharmacies-search-input"
          style={{ width: "100%", maxWidth: "480px", padding: "8px 12px", fontSize: "14px", border: "1px solid #d1d5db", borderRadius: "6px" }}
        />
      </div>
      {isLoading && <p data-testid="loading-indicator">Loading...</p>}
      {error && <p style={{ color: "#dc2626" }}>Error loading pharmacies.</p>}
      {!isLoading && !error && pharmacies.length === 0 && search.length >= 2 && (
        <p data-testid="no-results">No pharmacies found for &quot;{search}&quot;.</p>
      )}
      {!isLoading && !error && pharmacies.length === 0 && search.length < 2 && (
        <p data-testid="empty-hint" style={{ color: "#6b7280", fontSize: "14px" }}>
          Enter 2 or more characters to search pharmacies.
        </p>
      )}
      {pharmacies.length > 0 && (
        <div style={{ overflowX: "auto" }}>
          <table
            data-testid="pharmacies-list"
            style={{ width: "100%", borderCollapse: "collapse", fontSize: "14px" }}
          >
            <thead>
              <tr style={{ borderBottom: "2px solid #e5e7eb", textAlign: "left", backgroundColor: "#f9fafb" }}>
                <th style={{ padding: "8px 12px", fontWeight: 600, color: "#374151" }}>Name</th>
                <th style={{ padding: "8px 12px", fontWeight: 600, color: "#374151" }}>NPI</th>
                <th style={{ padding: "8px 12px", fontWeight: 600, color: "#374151" }}>NABP</th>
                <th style={{ padding: "8px 12px", fontWeight: 600, color: "#374151" }}>City</th>
                <th style={{ padding: "8px 12px", fontWeight: 600, color: "#374151" }}>State</th>
                <th style={{ padding: "8px 12px", fontWeight: 600, color: "#374151" }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {pharmacies.map((p, idx) => (
                <tr
                  key={p.npi}
                  data-testid="pharmacy-row"
                  onClick={() => onNavigate?.(`/directories/pharmacies/${p.npi}`)}
                  style={{
                    borderBottom: "1px solid #f3f4f6",
                    cursor: onNavigate ? "pointer" : "default",
                    backgroundColor: idx % 2 === 0 ? "#ffffff" : "#f9fafb",
                  }}
                >
                  <td style={{ padding: "8px 12px" }}>{p.display_name ?? p.legal_name ?? "-"}</td>
                  <td style={{ padding: "8px 12px", fontFamily: "monospace", fontSize: "13px" }}>{p.npi}</td>
                  <td style={{ padding: "8px 12px", fontFamily: "monospace", fontSize: "13px" }}>{p.nabp_number ?? "-"}</td>
                  <td style={{ padding: "8px 12px" }}>{p.city ?? "-"}</td>
                  <td style={{ padding: "8px 12px" }}>{p.state ?? "-"}</td>
                  <td style={{ padding: "8px 12px" }}>
                    <span style={{
                      padding: "2px 8px",
                      borderRadius: "9999px",
                      fontSize: "12px",
                      fontWeight: 500,
                      backgroundColor: p.status === "active" ? "#dcfce7" : "#f3f4f6",
                      color: p.status === "active" ? "#166534" : "#6b7280",
                    }}>
                      {p.status ?? "unknown"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p style={{ marginTop: "8px", fontSize: "12px", color: "#6b7280" }}>
            {pharmacies.length} result{pharmacies.length !== 1 ? "s" : ""}
          </p>
        </div>
      )}
    </div>
  );
}
