// src/components/ExclusionAlertBadge.tsx
// Clickable badge linking to /directories/exclusions?q=<npi|entity> when
// a prescriber or entity appears in one or more exclusion sources.
import React from "react";

export type ExclusionSource =
  | "cms_opt_out"
  | "sam_exclusions"
  | "ofac_sdn"
  | "oig_leie"
  | "dea_registrations";

export interface ExclusionAlertBadgeProps {
  npi?: string;
  entityName?: string;
  exclusionSources: ExclusionSource[];
}

export function ExclusionAlertBadge({ npi, entityName, exclusionSources }: ExclusionAlertBadgeProps) {
  if (exclusionSources.length === 0) return null;

  const query = npi ?? entityName ?? "";
  const href = `/directories/exclusions?q=${encodeURIComponent(query)}`;
  const label = `Excluded (${exclusionSources.length} source${exclusionSources.length === 1 ? "" : "s"})`;

  return (
    <a
      className="exclusion-alert-badge"
      href={href}
      title={`Found in: ${exclusionSources.join(", ")}`}
      aria-label={`Exclusion alert: ${label} — ${exclusionSources.join(", ")}`}
    >
      <span className="exclusion-alert-badge__icon" aria-hidden="true">⚠️</span>
      <span className="exclusion-alert-badge__label">{label}</span>
    </a>
  );
}
