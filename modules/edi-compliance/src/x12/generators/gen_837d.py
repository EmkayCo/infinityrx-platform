"""837D Dental Claim generator per 005010X224A3.

Builds ADA dental claims with tooth/surface coding.
All amounts Decimal with ROUND_HALF_UP. Validates before returning.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import List, Optional

from ..delimiters import Delimiters, _DEFAULT_DELIMITERS
from ..envelope import build_ge, build_gs, build_iea, build_se, build_st
from ..segments import build_segment, pad_isa_control, pad_isa_id
from .schemas import Generate837DRequest


def _fmt(amount: Decimal) -> str:
    return str(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _build_isa(req: Generate837DRequest, delims: Delimiters, now: datetime) -> str:
    elements = [
        "00", "          ", "00", "          ",
        req.sender_qualifier, pad_isa_id(req.sender_id),
        req.receiver_qualifier, pad_isa_id(req.receiver_id),
        now.strftime("%y%m%d"), now.strftime("%H%M"),
        "^", "00501", pad_isa_control(req.isa_control_number),
        "0", "T" if req.test_mode else "P", delims.sub_element,
    ]
    return build_segment("ISA", elements, delims)


def generate_837d(
    req: Generate837DRequest,
    delims: Optional[Delimiters] = None,
    now: Optional[datetime] = None,
) -> str:
    """Generate a complete 837D EDI file string (dental claims)."""
    if delims is None:
        delims = _DEFAULT_DELIMITERS
    if now is None:
        now = datetime.now(timezone.utc)

    segs: List[str] = []

    segs.append(_build_isa(req, delims, now))
    segs.append(build_gs("HC", req.sender_id.strip(), req.receiver_id.strip(),
                         req.gs_control_number, now, req.implementation_guide, delims))
    st_num = req.st_control_number
    segs.append(build_st("837", st_num, req.implementation_guide, delims))

    segs.append(build_segment("BHT", [
        "0019", "00",
        f"DENT{req.isa_control_number:09d}",
        now.strftime("%Y%m%d"), now.strftime("%H%M%S"),
        "CH",  # BHT06 claim/encounter
    ], delims))

    hl_counter = 0

    # HL 1 — billing provider
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
    segs.append(build_segment("SBR", ["P", "18", "", "", "", "", "", "", "DI"], delims))
    segs.append(build_segment("NM1", [
        "IL", "1",
        req.subscriber_last_name, req.subscriber_first_name, "", "", "",
        "MI", req.subscriber_id,
    ], delims))
    segs.append(build_segment("DMG", ["D8", req.subscriber_dob, req.subscriber_gender], delims))
    segs.append(build_segment("NM1", [
        "PR", "2",
        req.payer_name, "", "", "", "",
        "PI", req.payer_id,
    ], delims))

    # Claims
    for claim in req.claims:
        claim_id = claim.get("claim_id", "")
        charge = Decimal(str(claim.get("charge_amount", "0")))
        area_code = claim.get("oral_cavity_code", "00")
        svc_lines = claim.get("service_lines", [])

        segs.append(build_segment("CLM", [
            claim_id, _fmt(charge), "", "",
            f"11:B:1", "Y", "A", "Y", "I",
        ], delims))

        # Dental service lines — SV3 for dental
        for svc in svc_lines:
            ada_code = svc.get("procedure_code", "")
            svc_charge = Decimal(str(svc.get("charge_amount", "0")))
            tooth = svc.get("tooth_number", "")
            surface = svc.get("tooth_surface", "")
            svc_date = svc.get("date_of_service", "")

            sv3_elems = [f"AD:{ada_code}", _fmt(svc_charge), area_code, tooth, surface]
            segs.append(build_segment("SV3", sv3_elems, delims))
            if svc_date:
                segs.append(build_segment("DTP", ["472", "D8", svc_date], delims))

    body_count = len(segs) - 2
    segs.append(build_se(body_count + 1, st_num, delims))
    segs.append(build_ge(1, req.gs_control_number, delims))
    segs.append(build_iea(req.isa_control_number, 1, delims))

    result = "".join(segs)

    from ..validators.validator import validate_837d_basic
    errors = validate_837d_basic(result, delims)
    if errors:
        raise ValueError(f"Generated 837D failed validation: {errors}")

    return result
