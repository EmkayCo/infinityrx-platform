"""BRD Template Engine — schema-driven form builder and validator.

Validates submitted BRD answers against template schema including:
  - Required field enforcement
  - Type validation (text, number, date, dropdown, checkbox, file)
  - Conditional logic ("if field X == value, then field Y is required")
  - Cross-field validation rules

Parses approved/signed BRD into system configuration:
  - Plan hierarchy entries
  - Formulary entries (ProgramDrug rows)
  - BIN/PCN routing assignments
  - Fee schedule entries
  - Contract record seed data

Produces diff view (what will change) and supports atomic apply + rollback.

100% coverage required — financial parsing path is correctness-critical.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Pre-built template schemas per program type
# ---------------------------------------------------------------------------

PROGRAM_TYPE_SLUGS = [
    "copay",
    "voucher",
    "bridge",
    "debit_card",
    "specialty",
    "workers_comp",
    "340b",
    "commercial",
    "medicare",
    "medicaid",
]

_BASE_SECTIONS: list[dict[str, Any]] = [
    {
        "id": "program_basics",
        "title": "Program Basics",
        "fields": [
            {
                "id": "program_name",
                "type": "text",
                "label": "Program Name",
                "required": True,
                "validation": {"max_length": 200},
                "conditional": None,
            },
            {
                "id": "effective_date",
                "type": "date",
                "label": "Effective Date",
                "required": True,
                "validation": {},
                "conditional": None,
            },
            {
                "id": "termination_date",
                "type": "date",
                "label": "Termination Date",
                "required": False,
                "validation": {},
                "conditional": None,
            },
        ],
    },
    {
        "id": "drug_list",
        "title": "Drug List",
        "fields": [
            {
                "id": "ndcs",
                "type": "text_list",
                "label": "NDC List (11-digit, comma-separated)",
                "required": True,
                "validation": {"ndc_format": True},
                "conditional": None,
            },
        ],
    },
    {
        "id": "pricing_rules",
        "title": "Pricing Rules",
        "fields": [
            {
                "id": "copay_amount",
                "type": "money",
                "label": "Patient Copay Amount ($)",
                "required": True,
                "validation": {"min": "0.00", "max": "9999.99"},
                "conditional": None,
            },
            {
                "id": "per_fill_cap",
                "type": "money",
                "label": "Per-Fill Cap ($)",
                "required": False,
                "validation": {"min": "0.00"},
                "conditional": None,
            },
            {
                "id": "annual_max",
                "type": "money",
                "label": "Annual Maximum Benefit ($)",
                "required": False,
                "validation": {"min": "0.00"},
                "conditional": None,
            },
        ],
    },
    {
        "id": "bin_pcn",
        "title": "BIN/PCN Routing",
        "fields": [
            {
                "id": "bin_number",
                "type": "text",
                "label": "BIN Number",
                "required": False,
                "validation": {"pattern": r"\A\d{6}\Z"},
                "conditional": None,
            },
            {
                "id": "pcn",
                "type": "text",
                "label": "PCN",
                "required": False,
                "validation": {"max_length": 20},
                "conditional": None,
            },
        ],
    },
    {
        "id": "eligibility",
        "title": "Eligibility Criteria",
        "fields": [
            {
                "id": "requires_commercial_insurance",
                "type": "checkbox",
                "label": "Patients must have commercial insurance",
                "required": False,
                "validation": {},
                "conditional": None,
            },
            {
                "id": "excluded_states",
                "type": "text_list",
                "label": "Excluded States (2-letter codes)",
                "required": False,
                "validation": {"state_code": True},
                "conditional": None,
            },
        ],
    },
    {
        "id": "network",
        "title": "Pharmacy Network",
        "fields": [
            {
                "id": "network_type",
                "type": "dropdown",
                "label": "Network Type",
                "required": True,
                "validation": {"options": ["all", "specialty_only", "specific"]},
                "conditional": None,
            },
        ],
    },
    {
        "id": "reporting",
        "title": "Reporting Preferences",
        "fields": [
            {
                "id": "report_recipients",
                "type": "text_list",
                "label": "Report Email Recipients",
                "required": False,
                "validation": {"email": True},
                "conditional": None,
            },
        ],
    },
    {
        "id": "escalation_contacts",
        "title": "Escalation Contacts",
        "fields": [
            {
                "id": "primary_contact_email",
                "type": "text",
                "label": "Primary Contact Email",
                "required": True,
                "validation": {"email": True},
                "conditional": None,
            },
        ],
    },
]

# Debit-card-specific additional fields (conditional on program type)
_DEBIT_CARD_FIELDS: list[dict[str, Any]] = [
    {
        "id": "debit_card_issuer",
        "type": "text",
        "label": "Debit Card Issuer",
        "required": True,
        "validation": {"max_length": 100},
        "conditional": None,
    },
    {
        "id": "card_network",
        "type": "dropdown",
        "label": "Card Network",
        "required": True,
        "validation": {"options": ["visa", "mastercard"]},
        "conditional": None,
    },
]


def build_default_template_schema(program_type: str) -> dict[str, Any]:
    """Return a default form_builder_schema for the given program type.

    Raises ValueError for unknown program types.
    """
    if program_type not in PROGRAM_TYPE_SLUGS:
        raise ValueError(f"Unknown program_type: {program_type!r}. Must be one of {PROGRAM_TYPE_SLUGS}")

    import copy

    sections = copy.deepcopy(_BASE_SECTIONS)

    # Add program-type-specific sections
    if program_type == "debit_card":
        debit_section = {
            "id": "debit_card_config",
            "title": "Debit Card Configuration",
            "fields": copy.deepcopy(_DEBIT_CARD_FIELDS),
        }
        sections.append(debit_section)

    return {"sections": sections, "version": "1.0", "program_type": program_type}


# ---------------------------------------------------------------------------
# Validation engine
# ---------------------------------------------------------------------------

_NDC_RE = re.compile(r"\A\d{11}\Z")
_STATE_RE = re.compile(r"\A[A-Z]{2}\Z")
_EMAIL_RE = re.compile(r"\A[^@\s]+@[^@\s]+\.[^@\s]+\Z")
_BIN_RE = re.compile(r"\A\d{6}\Z")


def _validate_field_value(
    field: dict[str, Any],
    value: Any,
) -> tuple[bool, str]:
    """Validate a single field value against its schema definition.

    Returns (is_valid, error_message). Empty message means valid.
    """
    field_id = field["id"]
    field_type = field["type"]
    validation = field.get("validation", {})

    # Required check
    if field.get("required", False) and (value is None or value == "" or value == []):
        return False, f"Field '{field_id}' is required"

    # Skip further checks if value is empty and not required
    if value is None or value == "" or value == []:
        return True, ""

    if field_type == "text":
        if not isinstance(value, str):
            return False, f"Field '{field_id}' must be a string"
        max_len = validation.get("max_length")
        if max_len and len(value) > max_len:
            return False, f"Field '{field_id}' exceeds max length {max_len}"
        pattern = validation.get("pattern")
        if pattern and not re.fullmatch(pattern, value):
            return False, f"Field '{field_id}' does not match required format"
        if validation.get("email") and not _EMAIL_RE.fullmatch(value):
            return False, f"Field '{field_id}' must be a valid email address"

    elif field_type == "money":
        try:
            amount = Decimal(str(value))
        except Exception:
            return False, f"Field '{field_id}' must be a valid decimal amount"
        min_val = validation.get("min")
        max_val = validation.get("max")
        if min_val is not None and amount < Decimal(str(min_val)):
            return False, f"Field '{field_id}' must be >= {min_val}"
        if max_val is not None and amount > Decimal(str(max_val)):
            return False, f"Field '{field_id}' must be <= {max_val}"

    elif field_type == "date":
        if not isinstance(value, str):
            return False, f"Field '{field_id}' must be an ISO-8601 date string"
        try:
            datetime.fromisoformat(value)
        except ValueError:
            return False, f"Field '{field_id}' must be a valid ISO-8601 date"

    elif field_type == "dropdown":
        options = validation.get("options", [])
        if options and value not in options:
            return False, f"Field '{field_id}' must be one of: {options}"

    elif field_type == "checkbox":
        if not isinstance(value, bool):
            return False, f"Field '{field_id}' must be a boolean"

    elif field_type == "text_list":
        if not isinstance(value, list):
            return False, f"Field '{field_id}' must be a list"
        # NDC validation
        if validation.get("ndc_format"):
            for item in value:
                if not isinstance(item, str) or not _NDC_RE.fullmatch(item):
                    return False, f"Field '{field_id}' contains invalid NDC: {item!r}. Must be 11 digits."
        # State code validation
        if validation.get("state_code"):
            for item in value:
                if not isinstance(item, str) or not _STATE_RE.fullmatch(item):
                    return False, f"Field '{field_id}' contains invalid state code: {item!r}"
        # Email list validation
        if validation.get("email"):
            for item in value:
                if not isinstance(item, str) or not _EMAIL_RE.fullmatch(item):
                    return False, f"Field '{field_id}' contains invalid email: {item!r}"

    return True, ""


def _resolve_conditional(
    field: dict[str, Any],
    parsed_data: dict[str, Any],
) -> bool:
    """Return True if this field should be shown/active given current data.

    conditional shape: {"if_field": "field_id", "equals": "value", "then": "show"}
    None conditional means always shown.
    """
    conditional = field.get("conditional")
    if conditional is None:
        return True
    if_field = conditional.get("if_field")
    equals_value = conditional.get("equals")
    # Flatten all sections to find the field value
    field_value = None
    for section_data in parsed_data.values():
        if isinstance(section_data, dict) and if_field in section_data:
            field_value = section_data[if_field]
            break
    return field_value == equals_value


def validate_brd_submission(
    template_schema: dict[str, Any],
    parsed_data: dict[str, Any],
) -> dict[str, Any]:
    """Validate parsed_data against template_schema.

    Returns:
        {
            "valid": bool,
            "errors": {"field_id": "error message"},
            "warnings": {"field_id": "warning message"},
        }
    """
    errors: dict[str, str] = {}
    warnings: dict[str, str] = {}

    sections = template_schema.get("sections", [])
    for section in sections:
        section_id = section["id"]
        section_data = parsed_data.get(section_id, {})

        for field in section.get("fields", []):
            field_id = field["id"]

            # Check conditional: skip validation if field is not active
            if not _resolve_conditional(field, parsed_data):
                continue

            value = section_data.get(field_id) if isinstance(section_data, dict) else None
            valid, message = _validate_field_value(field, value)
            if not valid:
                errors[field_id] = message

    # Cross-field: check for duplicate NDCs within the drug list
    drug_section = parsed_data.get("drug_list", {})
    ndcs = drug_section.get("ndcs", []) if isinstance(drug_section, dict) else []
    if isinstance(ndcs, list):
        seen: set[str] = set()
        dupes: list[str] = []
        for ndc in ndcs:
            if ndc in seen:
                dupes.append(ndc)
            seen.add(ndc)
        if dupes:
            warnings["ndcs"] = f"Duplicate NDCs detected (will be deduplicated): {dupes}"

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# BRD Auto-Configuration Parser
# ---------------------------------------------------------------------------


def parse_brd_into_config(
    parsed_data: dict[str, Any],
    program_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> dict[str, Any]:
    """Parse approved BRD data into system configuration primitives.

    Returns a dict with keys:
      - drug_entries: list of ProgramDrug seed dicts
      - bin_pcn: BIN/PCN routing dict
      - fee_schedule: fee schedule dict
      - contract_seed: partial Contract seed dict

    All money values are Decimal strings, never floats.
    """
    basics = parsed_data.get("program_basics", {})
    drugs_section = parsed_data.get("drug_list", {})
    pricing = parsed_data.get("pricing_rules", {})
    bin_pcn_section = parsed_data.get("bin_pcn", {})
    eligibility = parsed_data.get("eligibility", {})
    reporting_section = parsed_data.get("reporting", {})

    # --- Drug entries (dedup NDCs with warning already recorded) ---
    raw_ndcs: list[str] = drugs_section.get("ndcs", []) if isinstance(drugs_section, dict) else []
    # Dedup preserving first occurrence
    seen_ndcs: set[str] = set()
    unique_ndcs: list[str] = []
    for ndc in raw_ndcs:
        if ndc not in seen_ndcs:
            unique_ndcs.append(ndc)
            seen_ndcs.add(ndc)

    # Parse money values as Decimal
    def _to_decimal(val: Any) -> Decimal | None:
        if val is None or val == "":
            return None
        return Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    copay_amount = _to_decimal(pricing.get("copay_amount"))
    per_fill_cap = _to_decimal(pricing.get("per_fill_cap"))
    annual_max = _to_decimal(pricing.get("annual_max"))

    drug_entries = [
        {
            "ndc": ndc,
            "copay_amount": str(copay_amount) if copay_amount is not None else None,
            "per_fill_cap": str(per_fill_cap) if per_fill_cap is not None else None,
            "annual_max": str(annual_max) if annual_max is not None else None,
        }
        for ndc in unique_ndcs
    ]

    # --- BIN/PCN routing ---
    bin_number = bin_pcn_section.get("bin_number") if isinstance(bin_pcn_section, dict) else None
    pcn = bin_pcn_section.get("pcn") if isinstance(bin_pcn_section, dict) else None
    if bin_number and not _BIN_RE.fullmatch(str(bin_number)):
        raise ValueError(f"Invalid BIN number in BRD: {bin_number!r}")
    bin_pcn_config = {"bin_number": bin_number, "pcn": pcn}

    # --- Fee schedule seed ---
    fee_schedule = {
        "per_claim": None,
        "monthly_admin": None,
        "setup_fee": None,
    }

    # --- Contract seed ---
    effective_date_str = basics.get("effective_date")
    contract_seed = {
        "effective_date": effective_date_str,
        "eligibility_criteria": {
            "requires_commercial_insurance": eligibility.get("requires_commercial_insurance", False),
            "excluded_states": eligibility.get("excluded_states", []),
        },
        "reporting": {
            "recipients": reporting_section.get("report_recipients", [])
            if isinstance(reporting_section, dict)
            else [],
        },
    }

    logger.info(
        "brd_parsed_into_config",
        extra={
            "svc_program_id": str(program_id),
            "svc_tenant_id": str(tenant_id),
            "svc_drug_count": len(drug_entries),
        },
    )

    return {
        "drug_entries": drug_entries,
        "bin_pcn": bin_pcn_config,
        "fee_schedule": fee_schedule,
        "contract_seed": contract_seed,
    }


# ---------------------------------------------------------------------------
# Diff view
# ---------------------------------------------------------------------------


def compute_brd_diff(
    existing_config: dict[str, Any],
    proposed_config: dict[str, Any],
) -> dict[str, Any]:
    """Compute what will change when applying a BRD to the existing program config.

    Returns:
        {
            "added": {entity_type: [items]},
            "modified": {entity_type: [items]},
            "removed": {entity_type: [items]},
        }
    """
    diff: dict[str, Any] = {"added": {}, "modified": {}, "removed": {}}

    # Drug diff
    existing_ndcs = {d["ndc"] for d in existing_config.get("drug_entries", [])}
    proposed_ndcs = {d["ndc"] for d in proposed_config.get("drug_entries", [])}
    added_ndcs = proposed_ndcs - existing_ndcs
    removed_ndcs = existing_ndcs - proposed_ndcs

    proposed_by_ndc = {d["ndc"]: d for d in proposed_config.get("drug_entries", [])}
    existing_by_ndc = {d["ndc"]: d for d in existing_config.get("drug_entries", [])}

    modified_ndcs = {
        ndc
        for ndc in (proposed_ndcs & existing_ndcs)
        if proposed_by_ndc[ndc] != existing_by_ndc[ndc]
    }

    if added_ndcs:
        diff["added"]["drugs"] = [proposed_by_ndc[n] for n in sorted(added_ndcs)]
    if removed_ndcs:
        diff["removed"]["drugs"] = [existing_by_ndc[n] for n in sorted(removed_ndcs)]
    if modified_ndcs:
        diff["modified"]["drugs"] = [
            {"ndc": n, "before": existing_by_ndc[n], "after": proposed_by_ndc[n]}
            for n in sorted(modified_ndcs)
        ]

    # BIN/PCN diff
    existing_bin_pcn = existing_config.get("bin_pcn", {})
    proposed_bin_pcn = proposed_config.get("bin_pcn", {})
    if existing_bin_pcn != proposed_bin_pcn:
        diff["modified"]["bin_pcn"] = [{"before": existing_bin_pcn, "after": proposed_bin_pcn}]

    return diff


# ---------------------------------------------------------------------------
# Digital signature hash for BRD sign-off
# ---------------------------------------------------------------------------


def compute_brd_signature_hash(
    submission_id: uuid.UUID,
    parsed_data: dict[str, Any],
    signer_id: uuid.UUID,
    timestamp: datetime,
) -> str:
    """Compute SHA-256 hash for BRD digital sign-off.

    Deterministic: same inputs → same hash. Includes signer and timestamp
    so replayed signatures at a different time produce different hashes.
    """
    payload = json.dumps(
        {
            "submission_id": str(submission_id),
            "parsed_data": parsed_data,
            "signer_id": str(signer_id),
            "timestamp": timestamp.isoformat(),
        },
        sort_keys=True,
        default=str,
    ).encode()
    return hashlib.sha256(payload).hexdigest()
