"""278 Health Care Services Review (Prior Authorization) generator per 005010X217.

Generates both 278 Request (BHT purpose code 13) and Response (BHT purpose code 11).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from ..delimiters import Delimiters, _DEFAULT_DELIMITERS
from ..envelope import build_ge, build_gs, build_iea, build_se, build_st
from ..segments import build_segment, pad_isa_control, pad_isa_id
from .schemas import Generate278Request


def _build_isa(req: Generate278Request, delims: Delimiters, now: datetime) -> str:
    elements = [
        "00", "          ", "00", "          ",
        req.sender_qualifier, pad_isa_id(req.sender_id),
        req.receiver_qualifier, pad_isa_id(req.receiver_id),
        now.strftime("%y%m%d"), now.strftime("%H%M"),
        "^", "00501", pad_isa_control(req.isa_control_number),
        "0", "T" if req.test_mode else "P", delims.sub_element,
    ]
    return build_segment("ISA", elements, delims)


def generate_278(
    req: Generate278Request,
    delims: Optional[Delimiters] = None,
    now: Optional[datetime] = None,
) -> str:
    """Generate a 278 prior authorization request or response."""
    if delims is None:
        delims = _DEFAULT_DELIMITERS
    if now is None:
        now = datetime.now(timezone.utc)

    segs: List[str] = []

    segs.append(_build_isa(req, delims, now))
    segs.append(build_gs("UM", req.sender_id.strip(), req.receiver_id.strip(),
                         req.gs_control_number, now, req.implementation_guide, delims))
    st_num = req.st_control_number
    segs.append(build_st("278", st_num, req.implementation_guide, delims))

    # BHT — purpose: 13=request, 11=response
    purpose_code = "11" if req.is_response else "13"
    segs.append(build_segment("BHT", [
        "0007",
        purpose_code,
        f"AUTH{req.isa_control_number:09d}",
        now.strftime("%Y%m%d"), now.strftime("%H%M"),
    ], delims))

    hl_counter = 0

    # HL 1 — information source (payer)
    hl_counter += 1
    segs.append(build_segment("HL", [str(hl_counter), "", "20", "1"], delims))
    segs.append(build_segment("NM1", [
        "PR", "2",
        req.payer_name, "", "", "", "",
        "PI", req.payer_id,
    ], delims))

    # HL 2 — provider
    hl_counter += 1
    segs.append(build_segment("HL", [str(hl_counter), "1", "19", "1"], delims))
    segs.append(build_segment("NM1", [
        "1P", "2",
        req.provider_name, "", "", "", "",
        "XX", req.provider_npi,
    ], delims))

    # HL 3 — subscriber
    hl_counter += 1
    has_reviews = len(req.service_reviews) > 0
    child_flag = "1" if has_reviews else "0"
    segs.append(build_segment("HL", [str(hl_counter), "2", "22", child_flag], delims))
    segs.append(build_segment("NM1", [
        "IL", "1",
        req.subscriber_last_name, req.subscriber_first_name, "", "", "",
        "MI", req.subscriber_id,
    ], delims))
    if req.subscriber_dob:
        segs.append(build_segment("DMG", ["D8", req.subscriber_dob], delims))

    # Service review lines
    for review in req.service_reviews:
        review_type = review.get("review_type", "HS")   # HS=health services review
        service_type = review.get("service_type_code", "")
        procedure_code = review.get("procedure_code", "")
        diagnosis = review.get("diagnosis_code", "")
        units = str(review.get("units", "1"))
        from_date = review.get("from_date", "")
        to_date = review.get("to_date", "")
        auth_number = review.get("authorization_number", "")

        # HL 4 — service
        hl_counter += 1
        segs.append(build_segment("HL", [str(hl_counter), str(hl_counter - 1), "SS", "0"], delims))

        if service_type:
            segs.append(build_segment("UM", [
                review_type, "I", service_type,
            ], delims))

        if procedure_code:
            segs.append(build_segment("HI", [f"BJ:{procedure_code}"], delims))

        if diagnosis:
            segs.append(build_segment("HI", [f"BK:{diagnosis}"], delims))

        if from_date:
            segs.append(build_segment("DTP", ["472", "D8", from_date], delims))
        if to_date:
            segs.append(build_segment("DTP", ["473", "D8", to_date], delims))

        segs.append(build_segment("QTY", ["VS", units], delims))

        # Authorization decision (response only)
        if req.is_response and auth_number:
            segs.append(build_segment("REF", ["BB", auth_number], delims))
        elif req.is_response:
            decision = review.get("decision", "A1")  # A1=approved, A3=denied, A4=pending
            segs.append(build_segment("HSD", [units, "DA", "", "", "", "", "", decision], delims))

    body_count = len(segs) - 2
    segs.append(build_se(body_count + 1, st_num, delims))
    segs.append(build_ge(1, req.gs_control_number, delims))
    segs.append(build_iea(req.isa_control_number, 1, delims))

    return "".join(segs)
