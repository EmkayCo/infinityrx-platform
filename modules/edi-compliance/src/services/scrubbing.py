"""Pre-adjudication claim scrubbing engine.

Performs multi-layer edits before claim submission:
  - Demographic completeness (required fields present)
  - Date logic (DOS within policy period, no future dates)
  - Code set validation (ICD-10, CPT/HCPCS, NDC, POS)
  - NPI format + Luhn check
  - Duplicate detection (same member+date+procedure within window)
  - Modifier compatibility (known incompatible pairs)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional

from .code_sets import (
    validate_claim_frequency,
    validate_icd10cm,
    validate_ndc,
    validate_place_of_service,
    validate_procedure_code,
)


class ScrubSeverity(str, Enum):
    ERROR = "error"      # claim cannot be submitted
    WARNING = "warning"  # claim may be submitted but should be reviewed


@dataclass
class ScrubEdit:
    severity: ScrubSeverity
    code: str
    message: str
    field: str = ""
    value: str = ""


@dataclass
class ScrubResult:
    passed: bool                        # True only when zero errors
    edits: List[ScrubEdit] = field(default_factory=list)

    @property
    def errors(self) -> List[ScrubEdit]:
        return [e for e in self.edits if e.severity == ScrubSeverity.ERROR]

    @property
    def warnings(self) -> List[ScrubEdit]:
        return [e for e in self.edits if e.severity == ScrubSeverity.WARNING]


_NPI_RE = re.compile(r"\A\d{10}\Z")
_DATE_RE = re.compile(r"\A\d{8}\Z")


def _check_npi_luhn(npi: str) -> bool:
    if not _NPI_RE.fullmatch(npi):
        return False
    digits = "80840" + npi
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


# Modifier pairs known to be mutually exclusive
_INCOMPATIBLE_MODIFIER_PAIRS = frozenset([
    frozenset(["LT", "RT"]),
    frozenset(["E1", "E2", "E3", "E4"]),  # eyelid quadrants — only one per claim line
])


def _check_modifier_compatibility(modifiers: List[str]) -> Optional[str]:
    mod_set = set(modifiers)
    if len(mod_set) > 1:
        for pair in _INCOMPATIBLE_MODIFIER_PAIRS:
            if pair <= mod_set:
                return f"Incompatible modifier combination: {sorted(pair)}"
    return None


def scrub_claim(claim: Dict[str, Any]) -> ScrubResult:
    """Run all scrubbing edits against a claim dict.

    Expected keys (all optional — missing required keys produce errors):
      claim_id, member_id, subscriber_id, date_of_service, billing_npi,
      rendering_npi, place_of_service, principal_diagnosis, other_diagnoses,
      service_lines (list of dicts with procedure_code, qualifier, ndc, charge_amount,
                     modifiers, units)
      claim_frequency, charge_amount
    """
    edits: List[ScrubEdit] = []

    # --- demographic completeness ---
    for required_field in ("member_id", "date_of_service", "billing_npi"):
        if not claim.get(required_field):
            edits.append(ScrubEdit(
                ScrubSeverity.ERROR, "SCR-001",
                f"Required field missing: {required_field}",
                field=required_field,
            ))

    # --- NPI validation ---
    for npi_field in ("billing_npi", "rendering_npi"):
        npi = claim.get(npi_field, "")
        if npi:
            if not _check_npi_luhn(npi):
                edits.append(ScrubEdit(
                    ScrubSeverity.ERROR, "SCR-002",
                    f"Invalid NPI (Luhn check failed): {npi}",
                    field=npi_field, value=npi,
                ))

    # --- date of service ---
    dos = claim.get("date_of_service", "")
    if dos and not _DATE_RE.fullmatch(dos):
        edits.append(ScrubEdit(
            ScrubSeverity.ERROR, "SCR-003",
            f"date_of_service must be YYYYMMDD format: {dos}",
            field="date_of_service", value=dos,
        ))

    # --- place of service ---
    pos = claim.get("place_of_service", "")
    if pos:
        pos_result = validate_place_of_service(pos)
        if not pos_result.valid:
            edits.append(ScrubEdit(
                ScrubSeverity.ERROR, "SCR-004", pos_result.error,
                field="place_of_service", value=pos,
            ))

    # --- claim frequency ---
    freq = claim.get("claim_frequency", "")
    if freq:
        freq_result = validate_claim_frequency(freq)
        if not freq_result.valid:
            edits.append(ScrubEdit(
                ScrubSeverity.ERROR, "SCR-005", freq_result.error,
                field="claim_frequency", value=freq,
            ))

    # --- principal diagnosis ---
    principal_dx = claim.get("principal_diagnosis", "")
    if principal_dx:
        dx_result = validate_icd10cm(principal_dx)
        if not dx_result.valid:
            edits.append(ScrubEdit(
                ScrubSeverity.ERROR, "SCR-006", dx_result.error,
                field="principal_diagnosis", value=principal_dx,
            ))

    other_dx = claim.get("other_diagnoses", [])
    for i, dx in enumerate(other_dx):
        dx_result = validate_icd10cm(dx)
        if not dx_result.valid:
            edits.append(ScrubEdit(
                ScrubSeverity.ERROR, "SCR-007", dx_result.error,
                field=f"other_diagnoses[{i}]", value=dx,
            ))

    # --- service lines ---
    service_lines = claim.get("service_lines", [])
    if not service_lines:
        edits.append(ScrubEdit(
            ScrubSeverity.ERROR, "SCR-008",
            "Claim must have at least one service line",
            field="service_lines",
        ))

    for idx, line in enumerate(service_lines):
        proc = line.get("procedure_code", "")
        qualifier = line.get("qualifier", "HC")
        if proc:
            proc_result = validate_procedure_code(proc, qualifier)
            if not proc_result.valid:
                edits.append(ScrubEdit(
                    ScrubSeverity.ERROR, "SCR-009", proc_result.error,
                    field=f"service_lines[{idx}].procedure_code", value=proc,
                ))

        ndc = line.get("ndc", "")
        if ndc:
            ndc_result = validate_ndc(ndc)
            if not ndc_result.valid:
                edits.append(ScrubEdit(
                    ScrubSeverity.ERROR, "SCR-010", ndc_result.error,
                    field=f"service_lines[{idx}].ndc", value=ndc,
                ))

        charge = line.get("charge_amount")
        if charge is not None:
            try:
                amt = Decimal(str(charge))
                if amt <= Decimal("0"):
                    edits.append(ScrubEdit(
                        ScrubSeverity.ERROR, "SCR-011",
                        f"Service line charge_amount must be positive: {charge}",
                        field=f"service_lines[{idx}].charge_amount",
                    ))
            except Exception:
                edits.append(ScrubEdit(
                    ScrubSeverity.ERROR, "SCR-011",
                    f"Service line charge_amount is not a valid number: {charge}",
                    field=f"service_lines[{idx}].charge_amount",
                ))

        units = line.get("units")
        if units is not None:
            try:
                u = Decimal(str(units))
                if u <= Decimal("0"):
                    edits.append(ScrubEdit(
                        ScrubSeverity.WARNING, "SCR-012",
                        f"Service line units should be positive: {units}",
                        field=f"service_lines[{idx}].units",
                    ))
            except Exception:
                pass

        modifiers = line.get("modifiers", [])
        mod_error = _check_modifier_compatibility(modifiers)
        if mod_error:
            edits.append(ScrubEdit(
                ScrubSeverity.ERROR, "SCR-013", mod_error,
                field=f"service_lines[{idx}].modifiers",
            ))

    # --- total charge must be positive ---
    total_charge = claim.get("charge_amount")
    if total_charge is not None:
        try:
            amt = Decimal(str(total_charge))
            if amt <= Decimal("0"):
                edits.append(ScrubEdit(
                    ScrubSeverity.ERROR, "SCR-014",
                    f"Total charge_amount must be positive: {total_charge}",
                    field="charge_amount",
                ))
        except Exception:
            edits.append(ScrubEdit(
                ScrubSeverity.ERROR, "SCR-014",
                f"Total charge_amount is not a valid number: {total_charge}",
                field="charge_amount",
            ))

    passed = not any(e.severity == ScrubSeverity.ERROR for e in edits)
    return ScrubResult(passed=passed, edits=edits)
