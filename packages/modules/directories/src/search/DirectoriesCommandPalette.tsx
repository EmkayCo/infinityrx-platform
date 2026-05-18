// src/search/DirectoriesCommandPalette.tsx
// Directories-aware wrapper around @infinityrx/ui CommandPalette.
// Adds grouped results by cluster, useDirectoriesSearch integration,
// B9 pending pill on blocked results, and "See all N in [cluster]" overflow links.
//
// Plan B spec §CommandPalette extension:
// - Groups by cluster (max 3 results visible per group)
// - "See all N in [dataset]" overflow link navigates to the browse surface
// - B9 blocked results show "[B9 pending]" suffix
// - Keyboard shortcut (Cmd+K / Ctrl+K) managed by DirectoriesCommandPaletteDialog
"use client";

import React, { useState, useEffect, useCallback } from "react";
import { CommandPalette, type CommandItem } from "@infinityrx/ui";
import { useDirectoriesSearch } from "./useDirectoriesSearch.js";
import type { SearchResultRecord, DatasetKey } from "./schemas.js";

// ── Cluster labels ────────────────────────────────────────────────────────────

const CLUSTER_LABELS: Record<DatasetKey, string> = {
  nppes: "Prescribers",
  ncpdp: "Pharmacies",
  fda_ndc: "Drugs",
  fda_orange_book: "Drugs",
  fda_purple_book: "Drugs",
  fda_drug_shortages: "Drugs",
  fda_rems: "Drugs",
  rxnorm: "Drugs",
  hcpcs: "Codes",
  icd10_cm: "Codes",
  cms_asp: "Pricing",
  cms_nadac: "Pricing",
  state_medicaid_bins: "Pricing",
  cms_opt_out: "Exclusions",
  ofac_sdn: "Exclusions",
  sam_exclusions: "Exclusions",
  oig_leie: "Exclusions",
  dea_registrations: "Exclusions",
};

// Canonical "See all" browse paths per dataset
const BROWSE_PATHS: Partial<Record<DatasetKey, string>> = {
  nppes: "/directories/prescribers",
  ncpdp: "/directories/pharmacies",
  fda_ndc: "/directories/drugs",
  hcpcs: "/directories/codes/hcpcs",
  icd10_cm: "/directories/codes/icd10",
  cms_asp: "/directories/pricing?tab=cms_asp",
  cms_nadac: "/directories/pricing?tab=cms_nadac",
  state_medicaid_bins: "/directories/pricing?tab=medicaid_bins",
  cms_opt_out: "/directories/exclusions?tab=cms_opt_out",
  ofac_sdn: "/directories/exclusions?tab=ofac_sdn",
  sam_exclusions: "/directories/exclusions?tab=sam_exclusions",
  oig_leie: "/directories/exclusions?tab=oig_leie",
  dea_registrations: "/directories/exclusions?tab=dea_registrations",
};

const DETAIL_PATHS: Partial<Record<DatasetKey, (id: string) => string>> = {
  nppes: (npi) => `/directories/prescribers/${npi}`,
  ncpdp: (nabp) => `/directories/pharmacies/${nabp}`,
  fda_ndc: (ndc) => `/directories/drugs/${ndc}`,
  hcpcs: (code) => `/directories/codes/hcpcs?code=${encodeURIComponent(code)}`,
  icd10_cm: (code) => `/directories/codes/icd10?code=${encodeURIComponent(code)}`,
  cms_opt_out: (id) => `/directories/exclusions?tab=cms_opt_out&id=${encodeURIComponent(id)}`,
  ofac_sdn: (id) => `/directories/exclusions?tab=ofac_sdn&id=${encodeURIComponent(id)}`,
  sam_exclusions: (id) => `/directories/exclusions?tab=sam_exclusions&id=${encodeURIComponent(id)}`,
  oig_leie: (id) => `/directories/exclusions?tab=oig_leie&id=${encodeURIComponent(id)}`,
  dea_registrations: (id) => `/directories/exclusions?tab=dea_registrations&id=${encodeURIComponent(id)}`,
};

/** Items per group before "See all" overflow is shown */
const MAX_PER_GROUP = 3;

// ── Types ────────────────────────────────────────────────────────────────────

export interface DirectoriesCommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Called when user selects a result or overflow link — receives the navigation href */
  onNavigate: (href: string) => void;
  placeholder?: string;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function recordToLabel(r: SearchResultRecord): string {
  const b9Suffix = r.b9_blocked ? " [B9 pending]" : "";
  const cluster = CLUSTER_LABELS[r.dataset] ?? r.dataset;
  return `${r.display}${b9Suffix} — ${cluster}`;
}

function recordToHref(r: SearchResultRecord): string {
  const builder = DETAIL_PATHS[r.dataset];
  return builder ? builder(r.id) : `/directories/${r.dataset}/${encodeURIComponent(r.id)}`;
}

/** Build flat CommandItem list with grouped structure (group headers + overflow links). */
function buildItems(results: SearchResultRecord[]): CommandItem[] {
  if (results.length === 0) return [];

  // Group by cluster label, preserving insertion order
  const groups = new Map<string, SearchResultRecord[]>();
  for (const r of results) {
    const label = CLUSTER_LABELS[r.dataset] ?? r.dataset;
    const existing = groups.get(label) ?? [];
    existing.push(r);
    groups.set(label, existing);
  }

  const items: CommandItem[] = [];
  for (const [cluster, recs] of groups) {
    // Group header (not selectable — id prefix prevents collision)
    items.push({ id: `__header__${cluster}`, label: `── ${cluster} ──` });

    const visible = recs.slice(0, MAX_PER_GROUP);
    for (const r of visible) {
      items.push({
        id: `result:${r.dataset}:${r.id}`,
        label: recordToLabel(r),
      });
    }

    // Overflow "See all N" link
    if (recs.length > MAX_PER_GROUP) {
      const overflowCount = recs.length - MAX_PER_GROUP;
      const browsePath = BROWSE_PATHS[recs[0].dataset] ?? `/directories/${recs[0].dataset}`;
      items.push({
        id: `__overflow__${cluster}`,
        label: `See all ${recs.length} in ${cluster} (+${overflowCount} more)`,
      });
      // Store browse path in id so onSelect can extract it
      items[items.length - 1] = {
        id: `__overflow__${cluster}__${browsePath}`,
        label: `See all ${recs.length} in ${cluster} (+${overflowCount} more)`,
      };
    }
  }

  return items;
}

// ── Component ─────────────────────────────────────────────────────────────────

export function DirectoriesCommandPalette({
  open,
  onOpenChange,
  onNavigate,
  placeholder = "Search directories…",
}: DirectoriesCommandPaletteProps) {
  const [query, setQuery] = useState("");

  // Reset query when palette closes
  useEffect(() => {
    if (!open) setQuery("");
  }, [open]);

  const { results, isLoading } = useDirectoriesSearch(query, {
    limit: 20,
    enabled: open,
  });

  const items = buildItems(results);

  const handleSelect = useCallback(
    (id: string) => {
      if (id.startsWith("__header__")) return; // group header — ignore
      if (id.startsWith("__overflow__")) {
        // Extract browse path from id: "__overflow__{cluster}__{path}"
        const parts = id.split("__");
        const browsePath = parts.slice(3).join("__"); // re-join in case path has __
        // Simpler: use the last __ segment which contains the path
        const pathSegment = id.replace(/^__overflow__[^_]+__(.*)$/, "$1");
        if (pathSegment && pathSegment !== id) {
          onNavigate(pathSegment);
        }
        onOpenChange(false);
        return;
      }
      // Regular result: "result:{dataset}:{id}"
      const withoutPrefix = id.replace(/^result:/, "");
      const colonIdx = withoutPrefix.indexOf(":");
      if (colonIdx === -1) return;
      const dataset = withoutPrefix.slice(0, colonIdx) as DatasetKey;
      const recordId = withoutPrefix.slice(colonIdx + 1);
      const href = DETAIL_PATHS[dataset]?.(recordId) ?? `/directories/${dataset}/${encodeURIComponent(recordId)}`;
      onNavigate(href);
      onOpenChange(false);
    },
    [onNavigate, onOpenChange]
  );

  return (
    <div data-testid="directories-command-palette">
      {isLoading && open && query.length >= 2 && (
        <span data-testid="dcp-loading" className="dcp-loading-indicator" />
      )}
      <CommandPalette
        open={open}
        onOpenChange={onOpenChange}
        items={items}
        onSelect={handleSelect}
        placeholder={placeholder}
      />
    </div>
  );
}
