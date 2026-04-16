"""NCPDP Telecommunications Standard D.0 parser and response builder.

Parses inbound D.0 claim requests into structured dataclasses and builds
conformant D.0 responses. Supports B1 (new billing), B2 (reversal),
B3 (rebill), and E1 (eligibility verification) transaction types.

NCPDP D.0 is a field-level protocol: each segment is a stream of
(field separator + field identifier + field data) tokens. The header
segment is fixed-position; all other segments use the segment/field
separator pattern.

References: NCPDP Telecommunication Standard Version D.0 Implementation Guide.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from shared.utils.money import ZERO, money

logger = logging.getLogger("adjudication_engine.ncpdp_parser")

# ---------------------------------------------------------------------------
# Protocol constants
# ---------------------------------------------------------------------------

FIELD_SEPARATOR = b"\x1c"  # ASCII FS — separates fields within a segment
GROUP_SEPARATOR = b"\x1d"  # ASCII GS — separates segments
SEGMENT_SEPARATOR = b"\x1e"  # ASCII RS — marks start of new segment

# Segment identifiers (AM field values)
SEGMENT_PATIENT = "01"
SEGMENT_INSURANCE = "04"
SEGMENT_CLAIM = "07"
SEGMENT_PRICING = "11"
SEGMENT_DUR_PPS = "08"
SEGMENT_PRESCRIBER = "03"
SEGMENT_PHARMACY = "02"

# Response segment IDs
RESP_STATUS = "20"
RESP_CLAIM = "21"
RESP_PRICING = "22"
RESP_DUR = "24"

# Response status codes
STATUS_ACCEPTED = "A"
STATUS_REJECTED = "R"
STATUS_PAID = "P"
STATUS_DUPLICATE = "D"

# NCPDP D.0 version identifier
VERSION_D0 = "D0"

# Valid transaction codes
VALID_TRANSACTION_CODES = {"B1", "B2", "B3", "E1"}

# Header field positions (fixed-position in D.0)
HEADER_LENGTH = 56

# ---------------------------------------------------------------------------
# Parsed claim dataclasses
# ---------------------------------------------------------------------------


@dataclass
class HeaderSegment:
    """NCPDP D.0 header segment (fixed-position fields)."""

    version: str = VERSION_D0
    transaction_code: str = ""  # B1/B2/B3/E1
    bin_number: str = ""  # 6-digit BIN
    pcn: str = ""  # Processor Control Number
    transaction_count: int = 1
    service_provider_id: str = ""  # pharmacy NPI or NCPDP ID
    date_of_service: str = ""  # CCYYMMDD


@dataclass
class PatientSegment:
    """NCPDP D.0 patient segment (01)."""

    cardholder_id: str = ""
    date_of_birth: str = ""  # CCYYMMDD
    gender_code: str = ""  # 1=male, 2=female
    person_code: str = ""  # 01=cardholder, 02=spouse, 03+=dependent
    patient_relationship: str = ""
    first_name: str = ""
    last_name: str = ""
    patient_id: str = ""


@dataclass
class InsuranceSegment:
    """NCPDP D.0 insurance segment (04)."""

    cardholder_id: str = ""
    group_id: str = ""
    cardholder_first_name: str = ""
    cardholder_last_name: str = ""
    plan_id: str = ""
    eligibility_clarification_code: str = ""
    other_coverage_code: str = ""  # COB indicator


@dataclass
class ClaimSegment:
    """NCPDP D.0 claim segment (07)."""

    prescription_number: str = ""
    ndc: str = ""  # 11-digit NDC
    quantity_dispensed: Decimal = ZERO
    days_supply: int = 0
    compound_code: str = ""  # 0=not compound, 1=compound, 2=N/A
    daw_code: str = ""  # dispense-as-written code
    date_prescription_written: str = ""  # CCYYMMDD
    refill_number: int = 0
    prescription_origin: str = ""
    fill_number: int = 0
    unit_of_measure: str = ""  # EA/GM/ML
    level_of_service: str = ""
    prior_authorization_type: str = ""
    prior_authorization_number: str = ""
    diagnosis_code: str = ""
    other_coverage_code: str = ""


@dataclass
class PricingSegment:
    """NCPDP D.0 pricing segment (11)."""

    ingredient_cost_submitted: Decimal = ZERO
    dispensing_fee_submitted: Decimal = ZERO
    patient_paid_amount: Decimal = ZERO
    usual_and_customary: Decimal = ZERO
    gross_amount_due: Decimal = ZERO
    basis_of_cost: str = ""  # 01=AWP, 02=local wholesaler, 03=direct, etc.
    incentive_amount_submitted: Decimal = ZERO
    other_amount_claimed: Decimal = ZERO
    flat_sales_tax_submitted: Decimal = ZERO
    percentage_sales_tax_submitted: Decimal = ZERO


@dataclass
class PrescriberSegment:
    """NCPDP D.0 prescriber segment (03)."""

    prescriber_id: str = ""  # NPI
    prescriber_id_qualifier: str = ""  # 01=NPI
    prescriber_last_name: str = ""
    prescriber_first_name: str = ""
    prescriber_phone: str = ""


@dataclass
class DURSegment:
    """NCPDP D.0 DUR/PPS segment (08)."""

    dur_pps_code_counter: int = 0
    reason_for_service_code: str = ""
    professional_service_code: str = ""
    result_of_service_code: str = ""
    dur_co_agent_id: str = ""
    dur_co_agent_qualifier: str = ""


@dataclass
class ParsedClaim:
    """Complete parsed NCPDP D.0 claim request.

    Aggregates all segments from a single transaction into one structure.
    The adjudication pipeline consumes this as its input.
    """

    header: HeaderSegment = field(default_factory=HeaderSegment)
    patient: PatientSegment = field(default_factory=PatientSegment)
    insurance: InsuranceSegment = field(default_factory=InsuranceSegment)
    claim: ClaimSegment = field(default_factory=ClaimSegment)
    pricing: PricingSegment = field(default_factory=PricingSegment)
    prescriber: PrescriberSegment = field(default_factory=PrescriberSegment)
    dur: DURSegment = field(default_factory=DURSegment)
    raw_segments: dict[str, dict[str, str]] = field(default_factory=dict)
    parse_errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Field parser helpers
# ---------------------------------------------------------------------------


def _safe_int(value: str, default: int = 0) -> int:
    """Parse an integer from a string, returning default on failure."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _safe_decimal(value: str) -> Decimal:
    """Parse a Decimal from an NCPDP monetary field.

    NCPDP monetary fields may include an implied decimal (last 2 digits
    are cents) or an explicit decimal point. We handle both.
    """
    if not value:
        return ZERO
    try:
        # Remove leading zeros but keep sign
        cleaned = value.strip()
        if not cleaned:
            return ZERO

        # NCPDP fields may use signed overpunch or explicit sign
        negative = False
        if cleaned.startswith("-") or cleaned.startswith("{"):
            negative = True
            cleaned = cleaned.lstrip("-{")
        if cleaned.endswith("}") or cleaned.endswith("-"):
            negative = True
            cleaned = cleaned.rstrip("}-")

        if "." in cleaned:
            result = money(Decimal(cleaned))
        else:
            # Implied decimal: last 2 digits are cents
            if len(cleaned) <= 2:
                result = money(Decimal(f"0.{cleaned.zfill(2)}"))
            else:
                result = money(Decimal(f"{cleaned[:-2]}.{cleaned[-2:]}"))

        return money(-result) if negative else result
    except (InvalidOperation, ValueError):
        return ZERO


def _parse_fields(segment_bytes: bytes) -> dict[str, str]:
    """Parse field-separated segment into {field_id: field_value} dict.

    Each field starts with 2-character field identifier followed by the value.
    Fields are separated by FIELD_SEPARATOR.
    """
    fields: dict[str, str] = {}
    raw = segment_bytes.decode("ascii", errors="replace")
    # Split on field separator character
    parts = raw.split("\x1c")
    for part in parts:
        if len(part) >= 2:
            field_id = part[:2]
            field_value = part[2:]
            fields[field_id] = field_value
    return fields


# ---------------------------------------------------------------------------
# Segment mappers
# ---------------------------------------------------------------------------


def _map_header(raw: bytes, claim: ParsedClaim) -> None:
    """Parse the fixed-position header from raw bytes."""
    if len(raw) < 4:
        claim.parse_errors.append("Header too short")
        return

    text = raw.decode("ascii", errors="replace")

    # D.0 header layout (variable, but key fields):
    # BIN (positions 0-5), Version (6-7), Transaction Code (8-9),
    # PCN (10+, variable length, terminated by FS)
    claim.header.bin_number = text[:6].strip() if len(text) >= 6 else ""
    claim.header.version = text[6:8].strip() if len(text) >= 8 else VERSION_D0
    claim.header.transaction_code = text[8:10].strip() if len(text) >= 10 else ""

    # PCN follows, up to next field separator
    remaining = text[10:]
    pcn_end = remaining.find("\x1c")
    if pcn_end > 0:
        claim.header.pcn = remaining[:pcn_end].strip()
    else:
        claim.header.pcn = remaining.strip()


def _map_patient(fields: dict[str, str], claim: ParsedClaim) -> None:
    """Map patient segment (01) fields to PatientSegment."""
    claim.patient.cardholder_id = fields.get("C2", "")
    claim.patient.date_of_birth = fields.get("C4", "")
    claim.patient.gender_code = fields.get("C5", "")
    claim.patient.person_code = fields.get("C6", "")
    claim.patient.patient_relationship = fields.get("C9", "")
    claim.patient.first_name = fields.get("CA", "")
    claim.patient.last_name = fields.get("CB", "")
    claim.patient.patient_id = fields.get("CX", "")


def _map_insurance(fields: dict[str, str], claim: ParsedClaim) -> None:
    """Map insurance segment (04) fields to InsuranceSegment."""
    claim.insurance.cardholder_id = fields.get("C2", "")
    claim.insurance.group_id = fields.get("C1", "")
    claim.insurance.cardholder_first_name = fields.get("CC", "")
    claim.insurance.cardholder_last_name = fields.get("CD", "")
    claim.insurance.plan_id = fields.get("FO", "")
    claim.insurance.eligibility_clarification_code = fields.get("C3", "")
    claim.insurance.other_coverage_code = fields.get("C8", "")


def _map_claim(fields: dict[str, str], claim: ParsedClaim) -> None:
    """Map claim segment (07) fields to ClaimSegment."""
    claim.claim.prescription_number = fields.get("D2", "")
    claim.claim.ndc = fields.get("D7", "")
    claim.claim.quantity_dispensed = _safe_decimal(fields.get("E7", "0"))
    claim.claim.days_supply = _safe_int(fields.get("D5", "0"))
    claim.claim.compound_code = fields.get("D6", "")
    claim.claim.daw_code = fields.get("D8", "")
    claim.claim.date_prescription_written = fields.get("DE", "")
    claim.claim.refill_number = _safe_int(fields.get("D3", "0"))
    claim.claim.prescription_origin = fields.get("DJ", "")
    claim.claim.fill_number = _safe_int(fields.get("D9", "0"))
    claim.claim.unit_of_measure = fields.get("DI", "")
    claim.claim.level_of_service = fields.get("DL", "")
    claim.claim.prior_authorization_type = fields.get("EU", "")
    claim.claim.prior_authorization_number = fields.get("EV", "")
    claim.claim.diagnosis_code = fields.get("DO", "")
    claim.claim.other_coverage_code = fields.get("C8", "")


def _map_pricing(fields: dict[str, str], claim: ParsedClaim) -> None:
    """Map pricing segment (11) fields to PricingSegment."""
    claim.pricing.ingredient_cost_submitted = _safe_decimal(fields.get("D9", "0"))
    claim.pricing.dispensing_fee_submitted = _safe_decimal(fields.get("DC", "0"))
    claim.pricing.patient_paid_amount = _safe_decimal(fields.get("DX", "0"))
    claim.pricing.usual_and_customary = _safe_decimal(fields.get("DQ", "0"))
    claim.pricing.gross_amount_due = _safe_decimal(fields.get("DU", "0"))
    claim.pricing.basis_of_cost = fields.get("DN", "")
    claim.pricing.incentive_amount_submitted = _safe_decimal(fields.get("E3", "0"))
    claim.pricing.flat_sales_tax_submitted = _safe_decimal(fields.get("HA", "0"))
    claim.pricing.percentage_sales_tax_submitted = _safe_decimal(fields.get("GE", "0"))


def _map_prescriber(fields: dict[str, str], claim: ParsedClaim) -> None:
    """Map prescriber segment (03) fields to PrescriberSegment."""
    claim.prescriber.prescriber_id = fields.get("DB", "")
    claim.prescriber.prescriber_id_qualifier = fields.get("DY", "")
    claim.prescriber.prescriber_last_name = fields.get("DR", "")
    claim.prescriber.prescriber_first_name = fields.get("2J", "")
    claim.prescriber.prescriber_phone = fields.get("PM", "")


def _map_dur(fields: dict[str, str], claim: ParsedClaim) -> None:
    """Map DUR/PPS segment (08) fields to DURSegment."""
    claim.dur.dur_pps_code_counter = _safe_int(fields.get("7E", "0"))
    claim.dur.reason_for_service_code = fields.get("E4", "")
    claim.dur.professional_service_code = fields.get("E5", "")
    claim.dur.result_of_service_code = fields.get("E6", "")
    claim.dur.dur_co_agent_id = fields.get("E7", "")
    claim.dur.dur_co_agent_qualifier = fields.get("RE", "")


# Segment ID -> mapper function
SEGMENT_MAPPERS = {
    SEGMENT_PATIENT: _map_patient,
    SEGMENT_INSURANCE: _map_insurance,
    SEGMENT_CLAIM: _map_claim,
    SEGMENT_PRICING: _map_pricing,
    SEGMENT_PRESCRIBER: _map_prescriber,
    SEGMENT_DUR_PPS: _map_dur,
    SEGMENT_PHARMACY: lambda fields, claim: None,  # pharmacy info from header
}


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------


def parse_d0_request(raw_bytes: bytes) -> ParsedClaim:
    """Parse an NCPDP D.0 request from raw bytes into a ParsedClaim.

    The parser is lenient: it collects parse_errors rather than raising
    on malformed input, allowing the adjudication pipeline to produce a
    meaningful rejection response.

    Args:
        raw_bytes: Raw bytes of the NCPDP D.0 request.

    Returns:
        ParsedClaim with all parsed segments and any parse errors.
    """
    result = ParsedClaim()

    if not raw_bytes:
        result.parse_errors.append("Empty request")
        return result

    if len(raw_bytes) < 10:
        result.parse_errors.append(f"Request too short: {len(raw_bytes)} bytes")
        return result

    # Split into segments on segment separator
    segments = raw_bytes.split(SEGMENT_SEPARATOR)

    # First part before any segment separator is the header
    if segments:
        _map_header(segments[0], result)

    # Validate transaction code
    if result.header.transaction_code not in VALID_TRANSACTION_CODES:
        result.parse_errors.append(
            f"Invalid transaction code: '{result.header.transaction_code}'"
        )

    # Parse remaining segments
    for seg_bytes in segments[1:]:
        if not seg_bytes:
            continue

        fields = _parse_fields(seg_bytes)
        segment_id = fields.get("AM", "")

        # Store raw fields
        result.raw_segments[segment_id] = fields

        # Map to typed segment
        mapper = SEGMENT_MAPPERS.get(segment_id)
        if mapper is not None:
            try:
                mapper(fields, result)
            except (ValueError, KeyError, TypeError) as exc:
                result.parse_errors.append(
                    f"Error parsing segment {segment_id}: {exc}"
                )
        else:
            logger.debug(
                "ncpdp.unknown_segment",
                extra={"svc_segment_id": segment_id},
            )

    # Extract service provider ID and date from header or pharmacy segment
    pharmacy_fields = result.raw_segments.get(SEGMENT_PHARMACY, {})
    if pharmacy_fields:
        result.header.service_provider_id = pharmacy_fields.get("D1", "")

    return result


# ---------------------------------------------------------------------------
# Response builder
# ---------------------------------------------------------------------------


@dataclass
class ClaimResponseData:
    """Input data for building an NCPDP D.0 response."""

    transaction_code: str = "B1"
    status: str = STATUS_ACCEPTED  # A/R/P/D
    authorization_number: str = ""
    reject_codes: list[str] = field(default_factory=list)
    reject_messages: list[str] = field(default_factory=list)
    ingredient_cost_paid: Decimal = ZERO
    dispensing_fee_paid: Decimal = ZERO
    patient_pay: Decimal = ZERO
    plan_pay: Decimal = ZERO
    total_amount: Decimal = ZERO
    dur_responses: list[dict[str, str]] = field(default_factory=list)
    bin_number: str = ""
    pcn: str = ""
    version: str = VERSION_D0


def build_d0_response(claim_result: ClaimResponseData) -> bytes:
    """Build an NCPDP D.0 response from adjudication results.

    Args:
        claim_result: Adjudication results to encode.

    Returns:
        Raw bytes of the NCPDP D.0 response.
    """
    parts: list[bytes] = []

    # Header: BIN + version + transaction response
    header = (
        f"{claim_result.bin_number:<6}"
        f"{claim_result.version:<2}"
        f"{claim_result.transaction_code:<2}"
    ).encode("ascii")
    parts.append(header)

    # Status segment (20)
    status_fields: list[str] = [
        f"AM{RESP_STATUS}",
        f"AN{claim_result.status}",
    ]
    if claim_result.authorization_number:
        status_fields.append(f"F3{claim_result.authorization_number}")

    # Add reject codes if rejected
    if claim_result.status == STATUS_REJECTED and claim_result.reject_codes:
        for i, code in enumerate(claim_result.reject_codes[:5]):  # max 5 per D.0
            status_fields.append(f"FA{code}")
        for msg in claim_result.reject_messages[:5]:
            status_fields.append(f"FB{msg}")

    parts.append(SEGMENT_SEPARATOR)
    parts.append(
        FIELD_SEPARATOR.join(f.encode("ascii") for f in status_fields)
    )

    # Claim response segment (21) — only for paid/accepted
    if claim_result.status in (STATUS_ACCEPTED, STATUS_PAID):
        claim_fields: list[str] = [
            f"AM{RESP_CLAIM}",
        ]
        parts.append(SEGMENT_SEPARATOR)
        parts.append(
            FIELD_SEPARATOR.join(f.encode("ascii") for f in claim_fields)
        )

    # Pricing response segment (22) — only for paid/accepted
    if claim_result.status in (STATUS_ACCEPTED, STATUS_PAID):
        pricing_fields: list[str] = [
            f"AM{RESP_PRICING}",
            f"F5{_format_money(claim_result.ingredient_cost_paid)}",
            f"F7{_format_money(claim_result.dispensing_fee_paid)}",
            f"F5{_format_money(claim_result.total_amount)}",
            f"F6{_format_money(claim_result.patient_pay)}",
            f"F9{_format_money(claim_result.plan_pay)}",
        ]
        parts.append(SEGMENT_SEPARATOR)
        parts.append(
            FIELD_SEPARATOR.join(f.encode("ascii") for f in pricing_fields)
        )

    # DUR response segment (24) — if any DUR results
    for dur_resp in claim_result.dur_responses:
        dur_fields: list[str] = [
            f"AM{RESP_DUR}",
        ]
        for key, value in dur_resp.items():
            dur_fields.append(f"{key}{value}")
        parts.append(SEGMENT_SEPARATOR)
        parts.append(
            FIELD_SEPARATOR.join(f.encode("ascii") for f in dur_fields)
        )

    return b"".join(parts)


def _format_money(amount: Decimal) -> str:
    """Format a Decimal amount for NCPDP monetary field.

    NCPDP uses a signed string with explicit decimal point.
    Negative values are prefixed with '-'.
    """
    formatted = str(money(amount))
    if amount < ZERO:
        return f"-{formatted.lstrip('-')}"
    return formatted
