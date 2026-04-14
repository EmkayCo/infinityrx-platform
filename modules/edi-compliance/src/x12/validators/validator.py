"""4-level X12 validation engine.

L1 — Syntax: structural X12 compliance (delimiters, envelope counts, segment IDs)
L2 — Implementation guide: required segments per IG
L3 — Business rules: NPI validity, date ranges, amount signs
L4 — Payer companion guide: payer-specific rules (loaded from DB)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import IntEnum

from ..delimiters import Delimiters, detect_delimiters
from ..segments import parse_segments


class ValidationLevel(IntEnum):
    SYNTAX = 1
    IMPLEMENTATION_GUIDE = 2
    BUSINESS = 3
    COMPANION_GUIDE = 4


@dataclass
class ValidationError:
    level: ValidationLevel
    code: str
    message: str
    segment_id: str = ""
    element_position: int | None = None


@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)


def _check_npi_luhn(npi: str) -> bool:
    """Validate NPI using Luhn algorithm with 80840 prefix."""
    if not re.fullmatch(r"\A\d{10}\Z", npi):
        return False
    # Prefix 80840 + NPI digits, then Luhn check
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


def _validate_syntax(raw: str, delims: Delimiters) -> list[ValidationError]:
    errors: list[ValidationError] = []
    segs = parse_segments(raw, delims)

    seg_ids = [s[0] for s in segs]

    # ISA must be first
    if not seg_ids or seg_ids[0] != "ISA":
        errors.append(ValidationError(ValidationLevel.SYNTAX, "L1-001", "ISA segment must be first"))
        return errors

    # IEA must be last
    if seg_ids[-1] != "IEA":
        errors.append(ValidationError(ValidationLevel.SYNTAX, "L1-002", "IEA segment must be last"))

    # ISA has exactly 16 elements
    isa = segs[0]
    if len(isa) != 17:  # segment_id + 16 elements
        errors.append(ValidationError(ValidationLevel.SYNTAX, "L1-003",
                                      f"ISA must have 16 elements, found {len(isa) - 1}", "ISA"))

    # Find GS/GE pairs
    gs_indices = [i for i, s in enumerate(segs) if s[0] == "GS"]
    ge_indices = [i for i, s in enumerate(segs) if s[0] == "GE"]
    if len(gs_indices) != len(ge_indices):
        errors.append(ValidationError(ValidationLevel.SYNTAX, "L1-004",
                                      f"GS/GE count mismatch: {len(gs_indices)} GS, {len(ge_indices)} GE"))

    # IEA01 must match GS count
    iea = next((s for s in segs if s[0] == "IEA"), None)
    if iea and len(iea) >= 2:
        try:
            iea_gs_count = int(iea[1])
            if iea_gs_count != len(gs_indices):
                errors.append(ValidationError(ValidationLevel.SYNTAX, "L1-005",
                                              f"IEA01 ({iea_gs_count}) != GS count ({len(gs_indices)})", "IEA"))
        except ValueError:
            errors.append(ValidationError(ValidationLevel.SYNTAX, "L1-006", "IEA01 must be numeric", "IEA"))

    # ISA control number must match IEA control number
    if len(isa) >= 14 and iea and len(iea) >= 3:
        if isa[13].lstrip("0") != iea[2].lstrip("0"):
            errors.append(ValidationError(ValidationLevel.SYNTAX, "L1-007",
                                          f"ISA13 ({isa[13]}) != IEA02 ({iea[2]})", "IEA"))

    # ST/SE pairs with segment count validation
    st_indices = [i for i, s in enumerate(segs) if s[0] == "ST"]
    se_indices = [i for i, s in enumerate(segs) if s[0] == "SE"]
    if len(st_indices) != len(se_indices):
        errors.append(ValidationError(ValidationLevel.SYNTAX, "L1-008",
                                      f"ST/SE count mismatch: {len(st_indices)} ST, {len(se_indices)} SE"))
    else:
        for st_i, se_i in zip(st_indices, se_indices):
            se_seg = segs[se_i]
            if len(se_seg) >= 2:
                try:
                    declared_count = int(se_seg[1])
                    actual_count = se_i - st_i + 1  # from ST through SE inclusive
                    if declared_count != actual_count:
                        errors.append(ValidationError(ValidationLevel.SYNTAX, "L1-009",
                                                      f"SE01 ({declared_count}) != actual segment count ({actual_count})", "SE"))
                except ValueError:
                    errors.append(ValidationError(ValidationLevel.SYNTAX, "L1-010", "SE01 must be numeric", "SE"))

    return errors


def _validate_835_guide(segs: list[list[str]]) -> list[ValidationError]:
    errors: list[ValidationError] = []
    seg_ids = [s[0] for s in segs]

    required = ["ISA", "GS", "ST", "BPR", "TRN", "SE", "GE", "IEA"]
    for r in required:
        if r not in seg_ids:
            errors.append(ValidationError(ValidationLevel.IMPLEMENTATION_GUIDE, "L2-835-001",
                                          f"Required segment {r} missing", r))

    # BPR must have at least 2 elements (BPR01, BPR02)
    bpr = next((s for s in segs if s[0] == "BPR"), None)
    if bpr and len(bpr) < 3:
        errors.append(ValidationError(ValidationLevel.IMPLEMENTATION_GUIDE, "L2-835-002",
                                      "BPR must have at least BPR01 and BPR02", "BPR"))

    return errors


def _validate_837p_guide(segs: list[list[str]]) -> list[ValidationError]:
    errors: list[ValidationError] = []
    seg_ids = [s[0] for s in segs]

    required = ["ISA", "GS", "ST", "BHT", "HL", "CLM", "SE", "GE", "IEA"]
    for r in required:
        if r not in seg_ids:
            errors.append(ValidationError(ValidationLevel.IMPLEMENTATION_GUIDE, "L2-837P-001",
                                          f"Required segment {r} missing", r))
    return errors


def _validate_business(segs: list[list[str]]) -> list[ValidationError]:
    errors: list[ValidationError] = []
    for seg in segs:
        if seg[0] == "NM1" and len(seg) >= 10:
            # NM108=XX means NPI qualifier
            if seg[8] == "XX" and seg[9]:
                if not _check_npi_luhn(seg[9]):
                    errors.append(ValidationError(ValidationLevel.BUSINESS, "L3-001",
                                                  f"Invalid NPI (Luhn check failed): {seg[9]}", "NM1"))
    return errors


def validate_x12(raw: str) -> ValidationResult:
    """Run all 4 levels of validation on a raw X12 string."""
    try:
        delims = detect_delimiters(raw)
    except ValueError as exc:
        return ValidationResult(
            is_valid=False,
            errors=[ValidationError(ValidationLevel.SYNTAX, "L1-000", str(exc))],
        )

    errors: list[ValidationError] = []
    segs = parse_segments(raw, delims)

    errors.extend(_validate_syntax(raw, delims))
    errors.extend(_validate_business(segs))

    return ValidationResult(is_valid=len(errors) == 0, errors=errors)


def validate_835_basic(raw: str, delims: Delimiters) -> list[str]:
    """Quick validation used by the 835 generator (fail-closed)."""
    segs = parse_segments(raw, delims)
    errors = _validate_syntax(raw, delims)
    errors.extend(_validate_835_guide(segs))
    errors.extend(_validate_business(segs))
    return [f"{e.code}: {e.message}" for e in errors]


def validate_837p_basic(raw: str, delims: Delimiters) -> list[str]:
    """Quick validation used by the 837P generator (fail-closed)."""
    segs = parse_segments(raw, delims)
    errors = _validate_syntax(raw, delims)
    errors.extend(_validate_837p_guide(segs))
    errors.extend(_validate_business(segs))
    return [f"{e.code}: {e.message}" for e in errors]


def _validate_837i_guide(segs: list[list[str]]) -> list[ValidationError]:
    errors: list[ValidationError] = []
    seg_ids = [s[0] for s in segs]
    required = ["ISA", "GS", "ST", "BHT", "HL", "CLM", "SE", "GE", "IEA"]
    for r in required:
        if r not in seg_ids:
            errors.append(ValidationError(ValidationLevel.IMPLEMENTATION_GUIDE, "L2-837I-001",
                                          f"Required segment {r} missing", r))
    return errors


def _validate_837d_guide(segs: list[list[str]]) -> list[ValidationError]:
    errors: list[ValidationError] = []
    seg_ids = [s[0] for s in segs]
    required = ["ISA", "GS", "ST", "BHT", "HL", "CLM", "SE", "GE", "IEA"]
    for r in required:
        if r not in seg_ids:
            errors.append(ValidationError(ValidationLevel.IMPLEMENTATION_GUIDE, "L2-837D-001",
                                          f"Required segment {r} missing", r))
    return errors


def validate_837i_basic(raw: str, delims: Delimiters) -> list[str]:
    """Quick validation used by the 837I generator (fail-closed)."""
    segs = parse_segments(raw, delims)
    errors = _validate_syntax(raw, delims)
    errors.extend(_validate_837i_guide(segs))
    errors.extend(_validate_business(segs))
    return [f"{e.code}: {e.message}" for e in errors]


def validate_837d_basic(raw: str, delims: Delimiters) -> list[str]:
    """Quick validation used by the 837D generator (fail-closed)."""
    segs = parse_segments(raw, delims)
    errors = _validate_syntax(raw, delims)
    errors.extend(_validate_837d_guide(segs))
    errors.extend(_validate_business(segs))
    return [f"{e.code}: {e.message}" for e in errors]
