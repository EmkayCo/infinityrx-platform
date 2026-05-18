// src/surfaces/exclusions/ExclusionsPage.tsx
// Unified exclusions browser with tabs: CMS Opt-Out, OFAC SDN, SAM Exclusions, OIG LEIE, DEA Registrations.
// Route: /directories/exclusions
//
// Execution-time verification findings:
// - cms_opt_out:     no REST route found in prescriber-directory/src/api/router.py
//                    (exclusion list checked inline at router.py:182 during NPI validation)
// - ofac_sdn:        OfacSdnEntry model exists in payment-processing/src/models/tables.py:212
//                    but no GET route exposes the SDN list
// - sam_exclusions:  no REST route found across all module routers
// - oig_leie:        no REST route found across all module routers
// - dea_registrations: no REST route found across all module routers
//
// All tabs render static reference cards until dedicated exclusion API routes are added.
// Each tab shows FreshnessChip for the relevant dataset key.
"use client";

import React, { useState } from "react";
import { FreshnessChip } from "../../components/FreshnessChip.js";

export interface ExclusionsPageProps {
  cms_opt_out_last_run_at?: string | null;
  ofac_sdn_last_run_at?: string | null;
  sam_exclusions_last_run_at?: string | null;
  oig_leie_last_run_at?: string | null;
  dea_registrations_last_run_at?: string | null;
}

type ExclusionTab =
  | "cms_opt_out"
  | "ofac_sdn"
  | "sam_exclusions"
  | "oig_leie"
  | "dea_registrations";

const TABS: { id: ExclusionTab; label: string }[] = [
  { id: "cms_opt_out", label: "CMS Opt-Out" },
  { id: "ofac_sdn", label: "OFAC SDN" },
  { id: "sam_exclusions", label: "SAM Exclusions" },
  { id: "oig_leie", label: "OIG LEIE" },
  { id: "dea_registrations", label: "DEA Registrations" },
];

const TAB_DESCRIPTIONS: Record<ExclusionTab, string> = {
  cms_opt_out:
    "Prescribers excluded from Medicare participation under CMS Opt-Out. NPI-level check enforced at adjudication.",
  ofac_sdn:
    "OFAC Specially Designated Nationals list. Screened at payment processing time via SDN name-match and fuzzy scoring.",
  sam_exclusions:
    "SAM.gov excluded entities. Federal award exclusions maintained by the General Services Administration.",
  oig_leie:
    "OIG List of Excluded Individuals/Entities. Individuals and entities excluded from participation in Federal health care programs.",
  dea_registrations:
    "DEA registrant data. Controlled substance authorization status for prescribers.",
};

export function ExclusionsPage({
  cms_opt_out_last_run_at,
  ofac_sdn_last_run_at,
  sam_exclusions_last_run_at,
  oig_leie_last_run_at,
  dea_registrations_last_run_at,
}: ExclusionsPageProps) {
  const [activeTab, setActiveTab] = useState<ExclusionTab>("cms_opt_out");

  const lastRunAtMap: Record<ExclusionTab, string | null | undefined> = {
    cms_opt_out: cms_opt_out_last_run_at,
    ofac_sdn: ofac_sdn_last_run_at,
    sam_exclusions: sam_exclusions_last_run_at,
    oig_leie: oig_leie_last_run_at,
    dea_registrations: dea_registrations_last_run_at,
  };

  return (
    <div data-testid="exclusions-page">
      <h1 data-testid="exclusions-title">Exclusions Reference</h1>

      {/* Tab bar */}
      <div data-testid="exclusions-tabs">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            data-testid={`tab-${tab.id}`}
            aria-selected={activeTab === tab.id}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div data-testid="tab-content">
        {TABS.map((tab) =>
          activeTab === tab.id ? (
            <div key={tab.id} data-testid={`${tab.id}-tab`}>
              <FreshnessChip
                sourceKey={tab.id}
                lastRunAt={lastRunAtMap[tab.id] ?? null}
              />
              <div data-testid={`${tab.id}-card`}>
                <h4 data-testid={`${tab.id}-title`}>
                  {TABS.find((t) => t.id === tab.id)?.label}
                </h4>
                <p data-testid={`${tab.id}-description`}>
                  {TAB_DESCRIPTIONS[tab.id]}
                </p>
                <p data-testid={`${tab.id}-no-route-note`}>
                  Live search is not yet available. Exclusion data is enforced at
                  adjudication time. Contact your InfinityRx administrator to
                  query this exclusion list directly.
                </p>
              </div>
            </div>
          ) : null
        )}
      </div>
    </div>
  );
}
