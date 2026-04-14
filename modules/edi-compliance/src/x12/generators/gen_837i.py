"""837I Institutional Claim generator per 005010X223A3.

Builds UB-04 based institutional claims (hospital inpatient/outpatient, SNF, home health).
All amounts Decimal with ROUND_HALF_UP. Validates before returning (fail-closed).
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Optional

from ..delimiters import Delimiters, _DEFAULT_DELIMITERS
from ..envelope import build_ge, build_gs, build_iea, build_se, build_st
from ..segments import build_segment, pad_isa_control, pad_isa_id
from .schemas import Generate837IRequest


def _fmt(amount: Decimal) -> str:
    return str(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _build_isa(req: Generate837IRequest, delims: Delimiters, now: datetime) -> str:
    elements = [
        "00", "          ", "00", "          ",
        req.sender_qualifier, pad_isa_id(req.sender_id),
        req.receiver_qualifier, pad_isa_id(req.receiver_id),
        now.strftime("%y%m%d"), now.strftime("%H%M"),
        "^", "00501", pad_isa_control(req.isa_control_number),
        "0", "T" if req.test_mode else "P", delims.sub_element,
    ]
    return build_segment("ISA", elements, delims)


def generate_837i(
    req: Generate837IRequest,
    delims: Optional[Delimiters] = None,
    now: Optional[datetime] = None,
) -> str:
    """Generate a complete 837I EDI file string (institutional claims)."""
    if delims is None:
        delims = _DEFAULT_DELIMITERS
    if now is None:
        now = datetime.now(timezone.utc)

    segs: List[str] = []

    # ISA/GS/ST
    segs.append(_build_isa(req, delims, now))
    segs.append(build_gs("HC", req.sender_id.strip(), req.receiver_id.strip(),
                         req.gs_control_number, now, req.implementation_guide, delims))
    st_num = req.st_control_number
    segs.append(build_st("837", st_num, req.implementation_guide, delims))

    # BHT — beginning of hierarchical transaction
    segs.append(build_segment("BHT", [
        "0019",                         # BHT01 hierarchical structure code
        "00",                           # BHT02 transaction set purpose (00=original)
        f"BATCH{req.isa_control_number:09d}",  # BHT03 reference identification
        now.strftime("%Y%m%d"),         # BHT04 date
        now.strftime("%H%M%S"),         # BHT05 time
        "RP",                           # BHT06 transaction type (RP=reporting)
    ], delims))

    hl_counter = 0

    # HL 1 — submitter (billing provider)
    hl_counter += 1
    segs.append(build_segment("HL", [str(hl_counter), "", "20", "1"], delims))
    segs.append(build_segment("NM1", [
        "85", "2",
        req.billing_provider_name, "", "", "", "",
        "XX", req.billing_provider_npi,
    ], delims))
    if req.billing_provider_ein:
        segs.append(build_segment("REF", ["EI", req.billing_provider_ein], delims))

    # HL 2 — subscriber
    hl_counter += 1
    segs.append(build_segment("HL", [str(hl_counter), "1", "22", "0"], delims))
    segs.append(build_segment("SBR", [
        "P", "18", "", "", "", "", "", "", req.claim_filing_indicator or "MC",
    ], delims))
    segs.append(build_segment("NM1", [
        "IL", "1",
        req.subscriber_last_name, req.subscriber_first_name, "", "", "",
        "MI", req.subscriber_id,
    ], delims))
    segs.append(build_segment("DMG", [
        "D8", req.subscriber_dob, req.subscriber_gender,
    ], delims))

    # Payer NM1
    segs.append(build_segment("NM1", [
        "PR", "2",
        req.payer_name, "", "", "", "",
        "PI", req.payer_id,
    ], delims))

    # Claims
    for claim in req.claims:
        claim_id = claim.get("claim_id", "")
        charge = Decimal(str(claim.get("charge_amount", "0")))
        facility_code = claim.get("facility_code", "21")
        admission_type = claim.get("admission_type", "1")
        admission_source = claim.get("admission_source", "7")
        patient_status = claim.get("patient_status", "01")
        admit_date = claim.get("admission_date", "")
        discharge_date = claim.get("discharge_date", "")
        principal_dx = claim.get("principal_diagnosis", "")
        drg = claim.get("drg_code", "")
        revenue_codes = claim.get("revenue_lines", [])

        # CLM segment
        segs.append(build_segment("CLM", [
            claim_id,
            _fmt(charge),
            "", "",
            f"{facility_code}:B:1",     # CLM05 facility/claim info
            "Y", "A", "Y", "I",
        ], delims))

        # Admission date
        if admit_date:
            segs.append(build_segment("DTP", ["435", "D8", admit_date], delims))
        if discharge_date:
            segs.append(build_segment("DTP", ["096", "D8", discharge_date], delims))

        # Diagnoses
        if principal_dx:
            segs.append(build_segment("HI", [
                f"ABK:{principal_dx}",
            ], delims))

        # DRG
        if drg:
            segs.append(build_segment("HI", [f"BBQ:{drg}"], delims))

        # Revenue lines (SV2 segments for institutional)
        for rev in revenue_codes:
            rev_code = rev.get("revenue_code", "")
            proc = rev.get("procedure_code", "")
            rev_charge = Decimal(str(rev.get("charge_amount", "0")))
            units = str(rev.get("units", "1"))
            svc_date = rev.get("date_of_service", "")
            svc01 = f"HC:{proc}" if proc else rev_code
            segs.append(build_segment("SV2", [
                rev_code, svc01, _fmt(rev_charge), "UN", units,
            ], delims))
            if svc_date:
                segs.append(build_segment("DTP", ["472", "D8", svc_date], delims))

    # SE
    body_count = len(segs) - 2  # exclude ISA, GS
    segs.append(build_se(body_count + 1, st_num, delims))
    segs.append(build_ge(1, req.gs_control_number, delims))
    segs.append(build_iea(req.isa_control_number, 1, delims))

    result = "".join(segs)

    from ..validators.validator import validate_837i_basic
    errors = validate_837i_basic(result, delims)
    if errors:
        raise ValueError(f"Generated 837I failed validation: {errors}")

    return result
