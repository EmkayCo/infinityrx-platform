"""PHI controls for reporting: masking, watermarking, access logging, export restrictions.

100% coverage required on all PHI paths.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

_VALID_ACCESS_TYPES = frozenset({"view", "download", "deliver", "preview", "api_access"})
_VALID_MASKING_LEVELS = frozenset({"full_detail", "partial", "redacted"})

_PHI_FIELDS: frozenset[str] = frozenset(
    {
        "member_name",
        "first_name",
        "last_name",
        "dob",
        "date_of_birth",
        "address",
        "address_line1",
        "address_line2",
        "city",
        "state",
        "zip",
        "zipcode",
        "phone",
        "phone_number",
        "email",
        "member_email",
        "ssn",
        "social_security",
        "member_id",
        "member_dob",
        "rx_number",
        "prescription_number",
        "ndc",
        "national_drug_code",
        "diagnosis_code",
        "icd_code",
        "prescriber_name",
        "prescriber_npi",
    }
)

_PARTIAL_MASKED_FIELDS = frozenset(
    {
        "dob",
        "date_of_birth",
        "address",
        "address_line1",
        "address_line2",
        "city",
        "state",
        "zip",
        "zipcode",
        "phone",
        "phone_number",
        "email",
        "ssn",
        "social_security",
    }
)

_AUTHORIZED_ROLES = frozenset({"tenant_admin", "operator", "system", "superadmin"})
_REDACTED_ROLES = frozenset({"client_portal", "client_user"})


def classify_report_phi_status(
    columns: list[dict[str, Any]],
    phi_fields_registry: set[str] | frozenset[str],
) -> bool:
    """Return True if any column in the report contains a PHI field."""
    return any(col.get("field", "").lower() in phi_fields_registry for col in columns)


def get_phi_masking_level(
    role: str,
    permissions: list[str] | None = None,
) -> str:
    """Determine the PHI masking level for a given user role."""
    if role in _REDACTED_ROLES:
        return "redacted"
    if role == "tenant_admin" or role == "system" or role == "superadmin":
        return "full_detail"
    if role == "operator":
        if permissions and "phi_access" in permissions:
            return "full_detail"
        return "partial"
    return "redacted"


def requires_watermark(contains_phi: bool, output_format: str) -> bool:
    """PHI PDF reports must be watermarked."""
    return contains_phi and output_format == "pdf"


def requires_export_restriction(
    contains_phi: bool,
    masking_level: str,
    role: str,
) -> bool:
    """Return True if the user cannot export this report."""
    if not contains_phi:
        return False
    return masking_level == "redacted"


def apply_phi_masking(
    row: dict[str, Any],
    masking_level: str,
    phi_fields: list[str] | frozenset[str],
) -> dict[str, Any]:
    """Apply PHI masking to a single data row."""
    if masking_level not in _VALID_MASKING_LEVELS:
        raise ValueError(f"Invalid masking level: {masking_level!r}")

    if masking_level == "full_detail":
        return dict(row)

    result = dict(row)
    for field in phi_fields:
        if field not in row:
            continue
        if masking_level == "redacted":
            result[field] = "[REDACTED]"
        elif masking_level == "partial" and field in _PARTIAL_MASKED_FIELDS:
            result[field] = "[MASKED]"

    return result


def log_phi_access(
    tenant_id: str,
    user_id: str,
    report_run_id: str,
    report_definition_id: str,
    access_type: str,
    masking_level: str,
    ip_address: str | None,
) -> dict[str, Any]:
    """Create a PHI access log entry (to be persisted by caller)."""
    if access_type not in _VALID_ACCESS_TYPES:
        raise ValueError(f"Invalid access_type: {access_type!r}")
    if masking_level not in _VALID_MASKING_LEVELS:
        raise ValueError(f"Invalid masking_level: {masking_level!r}")

    return {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "report_run_id": report_run_id,
        "report_definition_id": report_definition_id,
        "access_type": access_type,
        "masking_level": masking_level,
        "ip_address": ip_address,
        "accessed_at": datetime.now(UTC).isoformat(),
    }


class PhiControlsService:
    """Facade for PHI controls applied to reporting output."""

    def get_phi_fields(self) -> frozenset[str]:
        return _PHI_FIELDS

    def mask_row(self, row: dict[str, Any], masking_level: str) -> dict[str, Any]:
        return apply_phi_masking(row, masking_level, list(_PHI_FIELDS))

    def get_watermark_text(self) -> str:
        return "CONFIDENTIAL — CONTAINS PROTECTED HEALTH INFORMATION"

    def should_watermark(self, contains_phi: bool, output_format: str) -> bool:
        return requires_watermark(contains_phi, output_format)

    def masking_level_for_role(self, role: str, permissions: list[str] | None = None) -> str:
        return get_phi_masking_level(role, permissions)
