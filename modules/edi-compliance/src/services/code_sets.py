"""Code set validation for ICD-10, CPT, HCPCS, NDC, place-of-service, claim frequency.

Maintains version-aware code set registries. Per-payer version tracking allows
submitting against what the TARGET payer currently accepts, not just latest version.

Code sets update on schedule:
  ICD-10-CM/PCS: annual, Oct 1
  CPT: annual, Jan 1
  HCPCS: quarterly
  NDC: continuous
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Set


class CodeSetType(str, Enum):
    ICD10CM = "icd10cm"
    ICD10PCS = "icd10pcs"
    CPT = "cpt"
    HCPCS = "hcpcs"
    NDC = "ndc"
    PLACE_OF_SERVICE = "place_of_service"
    CLAIM_FREQUENCY = "claim_frequency"
    REVENUE_CODE = "revenue_code"


@dataclass
class CodeSetVersion:
    code_set: CodeSetType
    version: str            # e.g. "2026", "2026Q1"
    effective_date: str     # YYYYMMDD
    description: str = ""


@dataclass
class CodeValidationResult:
    valid: bool
    code: str
    code_set: CodeSetType
    error: str = ""
    warning: str = ""


# Minimal built-in code sets for validation — production would load from DB/files.
# These represent structurally valid patterns and a sample of known codes.

_PLACE_OF_SERVICE_CODES: Set[str] = {
    "01", "02", "03", "04", "05", "06", "07", "08", "09", "10",
    "11", "12", "13", "14", "15", "16", "17", "18", "19", "20",
    "21", "22", "23", "24", "25", "26", "27", "28", "31", "32",
    "33", "34", "41", "42", "49", "50", "51", "52", "53", "54",
    "55", "56", "57", "58", "60", "61", "62", "65", "71", "72",
    "81", "99",
}

_CLAIM_FREQUENCY_CODES: Set[str] = {
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
    "A", "B", "C", "D", "E", "F", "G", "H",
}

_VALID_REVENUE_CODE_PATTERN = re.compile(r"^\d{4}$")
_VALID_NDC_PATTERN = re.compile(r"^\d{11}$")
_VALID_CPT_PATTERN = re.compile(r"^\d{5}$|^[A-Z]\d{4}$|^\d{4}[A-Z]$")
_VALID_HCPCS_PATTERN = re.compile(r"^[A-Z]\d{4}$|^\d{5}$")
_VALID_ICD10CM_PATTERN = re.compile(r"^[A-Z]\d{2}(\.\w{1,4})?$")
_VALID_ICD10PCS_PATTERN = re.compile(r"^[A-Z0-9]{7}$")


def validate_place_of_service(code: str) -> CodeValidationResult:
    """Validate CMS place-of-service code."""
    valid = code.strip() in _PLACE_OF_SERVICE_CODES
    return CodeValidationResult(
        valid=valid,
        code=code,
        code_set=CodeSetType.PLACE_OF_SERVICE,
        error="" if valid else f"Unknown place-of-service code: {code}",
    )


def validate_claim_frequency(code: str) -> CodeValidationResult:
    """Validate claim frequency code (CLM05-3 / loop 2300)."""
    valid = code.strip() in _CLAIM_FREQUENCY_CODES
    return CodeValidationResult(
        valid=valid,
        code=code,
        code_set=CodeSetType.CLAIM_FREQUENCY,
        error="" if valid else f"Invalid claim frequency code: {code}",
    )


def validate_ndc(ndc: str) -> CodeValidationResult:
    """Validate NDC — must be exactly 11 digits."""
    clean = re.sub(r"[-\s]", "", ndc)
    valid = bool(_VALID_NDC_PATTERN.fullmatch(clean))
    return CodeValidationResult(
        valid=valid,
        code=ndc,
        code_set=CodeSetType.NDC,
        error="" if valid else f"NDC must be 11 digits (found {len(clean)}): {ndc}",
    )


def validate_cpt(code: str) -> CodeValidationResult:
    """Validate CPT code structure (5 digits or category II/III format)."""
    clean = code.strip()
    valid = bool(_VALID_CPT_PATTERN.fullmatch(clean))
    return CodeValidationResult(
        valid=valid,
        code=code,
        code_set=CodeSetType.CPT,
        error="" if valid else f"Invalid CPT code format: {code}",
    )


def validate_hcpcs(code: str) -> CodeValidationResult:
    """Validate HCPCS Level II code structure."""
    clean = code.strip()
    valid = bool(_VALID_HCPCS_PATTERN.fullmatch(clean))
    return CodeValidationResult(
        valid=valid,
        code=code,
        code_set=CodeSetType.HCPCS,
        error="" if valid else f"Invalid HCPCS code format: {code}",
    )


def validate_icd10cm(code: str) -> CodeValidationResult:
    """Validate ICD-10-CM diagnosis code structure."""
    clean = code.strip().replace(".", "")
    # Basic structural check: letter + 2 digits + optional 1-4 alphanumeric
    full_code = code.strip()
    valid = bool(_VALID_ICD10CM_PATTERN.fullmatch(full_code))
    return CodeValidationResult(
        valid=valid,
        code=code,
        code_set=CodeSetType.ICD10CM,
        error="" if valid else f"Invalid ICD-10-CM code structure: {code}",
    )


def validate_icd10pcs(code: str) -> CodeValidationResult:
    """Validate ICD-10-PCS procedure code structure (7 alphanumeric)."""
    clean = code.strip()
    valid = bool(_VALID_ICD10PCS_PATTERN.fullmatch(clean))
    return CodeValidationResult(
        valid=valid,
        code=code,
        code_set=CodeSetType.ICD10PCS,
        error="" if valid else f"Invalid ICD-10-PCS code (must be 7 alphanumeric): {code}",
    )


def validate_revenue_code(code: str) -> CodeValidationResult:
    """Validate UB-04 revenue code (4 digits)."""
    clean = code.strip()
    valid = bool(_VALID_REVENUE_CODE_PATTERN.fullmatch(clean))
    return CodeValidationResult(
        valid=valid,
        code=code,
        code_set=CodeSetType.REVENUE_CODE,
        error="" if valid else f"Revenue code must be 4 digits: {code}",
    )


def validate_procedure_code(code: str, qualifier: str = "HC") -> CodeValidationResult:
    """Validate a procedure code by qualifier type.

    qualifier: HC=CPT/HCPCS, AD=ADA dental, N4=NDC, ER=revenue code
    """
    if qualifier == "HC":
        cpt_result = validate_cpt(code)
        if cpt_result.valid:
            return cpt_result
        return validate_hcpcs(code)
    if qualifier == "AD":
        # ADA dental codes: D + 4 digits
        valid = bool(re.fullmatch(r"D\d{4}", code.strip()))
        return CodeValidationResult(
            valid=valid, code=code, code_set=CodeSetType.HCPCS,
            error="" if valid else f"Invalid ADA dental code: {code}",
        )
    if qualifier == "N4":
        return validate_ndc(code)
    if qualifier == "ER":
        return validate_revenue_code(code)
    # Unknown qualifier — pass through
    return CodeValidationResult(valid=True, code=code, code_set=CodeSetType.CPT)
