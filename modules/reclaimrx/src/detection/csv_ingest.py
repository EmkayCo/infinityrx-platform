"""CSV ingestion helpers: row entity resolution.

resolve_row() is a pure function -- no I/O, no DB, no side effects.

resolution_method values match the DB CHECK constraint:
    'declared' | 'group_id_lookup' | 'ndc_lookup' | 'manual' | 'unmapped'

v1 scope:
  - declared  : pharmacy_npi is present and non-empty.
  - unmapped  : pharmacy_npi is absent or empty.
  - resolved_client_id and resolved_program_id are always None -- raw
    integer client_id/program_id values are not coerced to UUIDs in v1.
    The raw values remain accessible via the original row dict.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ResolvedRow:
    """Result of resolving entity identifiers from a raw CSV row dict."""

    resolved_pharmacy_npi: Optional[str]
    resolved_ndc: Optional[str]
    # UUID columns -- always None in v1 (no int->UUID mapping implemented).
    resolved_client_id: Optional[str]
    resolved_program_id: Optional[str]
    # Must be one of: 'declared'|'group_id_lookup'|'ndc_lookup'|'manual'|'unmapped'
    resolution_method: str
    resolution_notes: Optional[str] = field(default=None)


def resolve_row(row: dict) -> ResolvedRow:
    """Resolve entity identifiers from a raw CSV row dictionary.

    Args:
        row: Dict of raw CSV column name -> string value.

    Returns:
        ResolvedRow with resolution_method 'declared' when pharmacy_npi is
        present and non-empty, or 'unmapped' otherwise.

    resolved_client_id and resolved_program_id are always None in v1.
    The raw client_id / program_id values stay in the caller's row dict.
    """
    raw_npi: str = row.get("pharmacy_npi", "") or ""
    raw_ndc: str = row.get("ndc", "") or ""

    npi_clean = raw_npi.strip() or None
    ndc_clean = raw_ndc.strip() or None

    if npi_clean:
        return ResolvedRow(
            resolved_pharmacy_npi=npi_clean,
            resolved_ndc=ndc_clean,
            resolved_client_id=None,
            resolved_program_id=None,
            resolution_method="declared",
            resolution_notes=None,
        )

    return ResolvedRow(
        resolved_pharmacy_npi=None,
        resolved_ndc=ndc_clean,
        resolved_client_id=None,
        resolved_program_id=None,
        resolution_method="unmapped",
        resolution_notes="missing pharmacy_npi",
    )
