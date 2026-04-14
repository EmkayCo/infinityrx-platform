"""277 Health Care Claim Status Response generator per 005010X212."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from ..delimiters import Delimiters, _DEFAULT_DELIMITERS
from ..envelope import build_ge, build_gs, build_iea, build_se, build_st
from ..segments import build_segment, pad_isa_control, pad_isa_id
from .schemas import Generate277Request


def _build_isa(req: Generate277Request, delims: Delimiters, now: datetime) -> str:
    elements = [
        "00", "          ", "00", "          ",
        req.sender_qualifier, pad_isa_id(req.sender_id),
        req.receiver_qualifier, pad_isa_id(req.receiver_id),
        now.strftime("%y%m%d"), now.strftime("%H%M"),
        "^", "00501", pad_isa_control(req.isa_control_number),
        "0", "T" if req.test_mode else "P", delims.sub_element,
    ]
    return build_segment("ISA", elements, delims)


# 277 claim status category codes (ANSI X12)
_STATUS_CATEGORY = {
    "A0": "Acknowledged",
    "A1": "Received",
    "A2": "Returned",
    "A3": "Not Found",
    "A4": "Not Processed",
    "A6": "Rejected",
    "A7": "Accepted",
    "A8": "Accepted With Changes",
    "F0": "Finalized",
    "F1": "Finalized — Payment",
    "F2": "Finalized — Denial",
    "F3": "Finalized — Revised",
    "P1": "Pending",
    "P2": "Pending — Patient Information",
    "P3": "Pending — Provider Information",
}


def generate_277(
    req: Generate277Request,
    delims: Optional[Delimiters] = None,
    now: Optional[datetime] = None,
) -> str:
    """Generate a 277 claim status response."""
    if delims is None:
        delims = _DEFAULT_DELIMITERS
    if now is None:
        now = datetime.now(timezone.utc)

    segs: List[str] = []

    segs.append(_build_isa(req, delims, now))
    segs.append(build_gs("HN", req.sender_id.strip(), req.receiver_id.strip(),
                         req.gs_control_number, now, req.implementation_guide, delims))
    st_num = req.st_control_number
    segs.append(build_st("277", st_num, req.implementation_guide, delims))

    segs.append(build_segment("BHT", [
        "0010", "08",
        f"RESP{req.isa_control_number:09d}",
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

    for status in req.claim_statuses:
        member_id = status.get("subscriber_id", "")
        member_last = status.get("subscriber_last_name", "")
        member_first = status.get("subscriber_first_name", "")
        claim_id = status.get("claim_id", "")
        provider_npi = status.get("provider_npi", "")
        provider_name = status.get("provider_name", "")
        status_code = status.get("status_category_code", "A0")
        status_info_code = status.get("status_code", "")
        dos = status.get("date_of_service", "")
        charge = status.get("charge_amount", "")
        paid = status.get("paid_amount", "")

        # HL — provider
        hl_counter += 1
        segs.append(build_segment("HL", [str(hl_counter), "1", "19", "1"], delims))
        segs.append(build_segment("NM1", [
            "1P", "2",
            provider_name, "", "", "", "",
            "XX", provider_npi,
        ], delims))

        # HL — subscriber
        hl_counter += 1
        segs.append(build_segment("HL", [str(hl_counter), str(hl_counter - 1), "22", "1"], delims))
        segs.append(build_segment("NM1", [
            "IL", "1",
            member_last, member_first, "", "", "",
            "MI", member_id,
        ], delims))

        # HL — claim
        hl_counter += 1
        segs.append(build_segment("HL", [str(hl_counter), str(hl_counter - 1), "23", "0"], delims))
        if dos:
            segs.append(build_segment("DTP", ["472", "D8", dos], delims))
        if claim_id:
            segs.append(build_segment("REF", ["1K", claim_id], delims))

        # STC — status information
        # STC01=status, STC02=date, STC03=action, STC04=charge, STC05-08 reserved, STC09=paid
        stc_01 = f"{status_code}{delims.sub_element}{status_info_code}" if status_info_code else status_code
        stc_elems = [stc_01, now.strftime("%Y%m%d"), "WQ", charge or "", "", "", "", "", paid or ""]
        segs.append(build_segment("STC", stc_elems, delims))

    body_count = len(segs) - 2
    segs.append(build_se(body_count + 1, st_num, delims))
    segs.append(build_ge(1, req.gs_control_number, delims))
    segs.append(build_iea(req.isa_control_number, 1, delims))

    return "".join(segs)
