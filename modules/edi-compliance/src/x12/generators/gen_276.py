"""276 Health Care Claim Status Request generator per 005010X212."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from ..delimiters import Delimiters, _DEFAULT_DELIMITERS
from ..envelope import build_ge, build_gs, build_iea, build_se, build_st
from ..segments import build_segment, pad_isa_control, pad_isa_id
from .schemas import Generate276Request


def _build_isa(req: Generate276Request, delims: Delimiters, now: datetime) -> str:
    elements = [
        "00", "          ", "00", "          ",
        req.sender_qualifier, pad_isa_id(req.sender_id),
        req.receiver_qualifier, pad_isa_id(req.receiver_id),
        now.strftime("%y%m%d"), now.strftime("%H%M"),
        "^", "00501", pad_isa_control(req.isa_control_number),
        "0", "T" if req.test_mode else "P", delims.sub_element,
    ]
    return build_segment("ISA", elements, delims)


def generate_276(
    req: Generate276Request,
    delims: Optional[Delimiters] = None,
    now: Optional[datetime] = None,
) -> str:
    """Generate a 276 claim status request."""
    if delims is None:
        delims = _DEFAULT_DELIMITERS
    if now is None:
        now = datetime.now(timezone.utc)

    segs: List[str] = []

    segs.append(_build_isa(req, delims, now))
    segs.append(build_gs("HR", req.sender_id.strip(), req.receiver_id.strip(),
                         req.gs_control_number, now, req.implementation_guide, delims))
    st_num = req.st_control_number
    segs.append(build_st("276", st_num, req.implementation_guide, delims))

    segs.append(build_segment("BHT", [
        "0010", "13",
        f"STATUS{req.isa_control_number:09d}",
        now.strftime("%Y%m%d"), now.strftime("%H%M"),
    ], delims))

    hl_counter = 0

    # HL 1 — information receiver (the requestor/submitter)
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

    # Per-claim inquiries
    for inquiry in req.claim_inquiries:
        member_id = inquiry.get("subscriber_id", "")
        member_last = inquiry.get("subscriber_last_name", "")
        member_first = inquiry.get("subscriber_first_name", "")
        claim_id = inquiry.get("claim_id", "")
        dos = inquiry.get("date_of_service", "")

        # HL 3 — subscriber
        hl_counter += 1
        segs.append(build_segment("HL", [str(hl_counter), "2", "22", "1"], delims))
        segs.append(build_segment("NM1", [
            "IL", "1",
            member_last, member_first, "", "", "",
            "MI", member_id,
        ], delims))

        # HL 4 — claim
        hl_counter += 1
        segs.append(build_segment("HL", [str(hl_counter), str(hl_counter - 1), "23", "0"], delims))
        if dos:
            segs.append(build_segment("DTP", ["472", "D8", dos], delims))
        if claim_id:
            segs.append(build_segment("REF", ["1K", claim_id], delims))

    body_count = len(segs) - 2
    segs.append(build_se(body_count + 1, st_num, delims))
    segs.append(build_ge(1, req.gs_control_number, delims))
    segs.append(build_iea(req.isa_control_number, 1, delims))

    return "".join(segs)
